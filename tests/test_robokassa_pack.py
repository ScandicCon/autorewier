"""Тесты эндпоинта покупки пакета VIN-отчётов через Robokassa.

Проверяется создание счёта и сборка ссылки оплаты. Начисление кредитов в
ResultURL-вебхуке использует тот же обработчик, что и активация Pro (покрыт
проверкой подписи в test_robokassa.py).
"""

import urllib.parse as up
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    import app.database as database
    from app.config import settings

    url = f"sqlite+aiosqlite:///{tmp_path / 'rkpack.db'}"
    engine = create_async_engine(url)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(settings, "database_url", url)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "async_session", sm)
    monkeypatch.setenv("ROBOKASSA_MERCHANT_LOGIN", "demo")
    monkeypatch.setenv("ROBOKASSA_PASSWORD1", "pw1")
    monkeypatch.setenv("ROBOKASSA_PASSWORD2", "pw2")
    monkeypatch.setenv("ROBOKASSA_TEST_MODE", "1")
    with TestClient(app) as c:
        yield c


def _h():
    return {"X-Telegram-Id": "880100"}


def test_buy_pack_returns_payment_url_with_correct_price(client):
    r = client.post("/api/v1/payments/robokassa/buy-pack", headers=_h(), json={"pack_size": 10})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["inv_id"]
    assert "auth.robokassa.ru" in body["payment_url"]
    q = dict(up.parse_qsl(body["payment_url"].split("?", 1)[1]))
    assert q["OutSum"] == "890.00"  # цена пакета 10 (REPORT_PACKS)
    assert q["SignatureValue"]
    assert q["Shp_user"]


def test_buy_pack_rejects_unknown_size(client):
    r = client.post("/api/v1/payments/robokassa/buy-pack", headers=_h(), json={"pack_size": 7})
    assert r.status_code == 400


def test_buy_pack_requires_auth(client):
    r = client.post("/api/v1/payments/robokassa/buy-pack", json={"pack_size": 10})
    assert r.status_code in (401, 403)
