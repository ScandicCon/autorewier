"""Тесты пробивки по гос-номеру (ГРЗ).

Валидация/нормализация — чистые функции. Эндпоинт проверяется в демо-режиме
(без ключей Autocode), поэтому платных вызовов не происходит.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.services import grz


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("а123вс777", "А123ВС777"),      # нижний регистр кириллица
        ("A123BC777", "А123ВС777"),      # латиница → кириллица
        ("а 123 вс 77", "А123ВС77"),     # пробелы, 2-значный регион
        ("Х999ХХ199", "Х999ХХ199"),
    ],
)
def test_normalize_plate(raw, expected):
    assert grz.normalize_plate(raw) == expected


@pytest.mark.parametrize(
    "plate,ok",
    [
        ("А123ВС777", True),
        ("A123BC77", True),
        ("123АВС77", False),     # начинается с цифр
        ("АБ123В77", False),     # недопустимые буквы/формат
        ("А123ВС", False),       # нет региона
        ("", False),
    ],
)
def test_is_valid_plate(plate, ok):
    assert grz.is_valid_plate(plate) is ok


@pytest.fixture()
def client(tmp_path: Path, monkeypatch):
    import app.database as database
    from app.config import settings

    url = f"sqlite+aiosqlite:///{tmp_path / 'grz.db'}"
    engine = create_async_engine(url)
    sm = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    monkeypatch.setattr(settings, "database_url", url)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "async_session", sm)
    with TestClient(app) as c:
        yield c


def _h():
    return {"X-Telegram-Id": "870100"}


def test_grz_check_demo_returns_report(client):
    r = client.post("/api/v1/grz/check", headers=_h(), json={"plate": "а123вс777"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["plate"] == "А123ВС777"
    assert "summary" in data
    assert data.get("demo") is True


def test_grz_check_rejects_invalid_plate(client):
    r = client.post("/api/v1/grz/check", headers=_h(), json={"plate": "не номер"})
    assert r.status_code == 400


def test_grz_check_requires_auth(client):
    r = client.post("/api/v1/grz/check", json={"plate": "А123ВС777"})
    assert r.status_code in (401, 403)
