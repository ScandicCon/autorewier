"""Тесты эндпоинта смены пароля по старому паролю (/auth/password-change)."""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.services.auth import COOKIE_NAME


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.database as database
    import app.services.inspections as inspections
    from app.config import settings

    db_file = tmp_path / "password_change.db"
    test_db_url = f"sqlite+aiosqlite:///{db_file}"
    test_engine = create_async_engine(test_db_url, echo=False)
    test_sessionmaker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(settings, "database_url", test_db_url)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "async_session", test_sessionmaker)

    async def _no_external_enrichment(report, vehicle, defects, user_preferences, listing_repairs):
        return report

    monkeypatch.setattr(inspections, "_enrich_report", _no_external_enrichment)

    with TestClient(app) as client:
        yield client

    asyncio.run(test_engine.dispose())


def _register_and_login(client: TestClient, email: str, password: str = "strongpass123") -> str:
    client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "password_confirm": password},
    )
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.cookies.get(COOKIE_NAME)
    assert token
    return token


def test_password_change_success(api_client: TestClient):
    """Верный старый пароль → пароль меняется, новый работает, старый — нет."""
    email = "change-ok@example.com"
    token = _register_and_login(api_client, email)

    resp = api_client.post(
        "/api/v1/auth/password-change",
        headers={"Cookie": f"{COOKIE_NAME}={token}"},
        json={"old_password": "strongpass123", "new_password": "brandnew456"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json().get("ok") is True

    # старый пароль больше не подходит
    bad = api_client.post("/api/v1/auth/login", json={"email": email, "password": "strongpass123"})
    assert bad.status_code == 401, bad.text
    # новый пароль работает
    good = api_client.post("/api/v1/auth/login", json={"email": email, "password": "brandnew456"})
    assert good.status_code == 200, good.text


def test_password_change_wrong_old(api_client: TestClient):
    """Неверный старый пароль → 400, пароль не меняется."""
    email = "change-wrong@example.com"
    token = _register_and_login(api_client, email)

    resp = api_client.post(
        "/api/v1/auth/password-change",
        headers={"Cookie": f"{COOKIE_NAME}={token}"},
        json={"old_password": "WRONGpass", "new_password": "brandnew456"},
    )
    assert resp.status_code == 400, resp.text
    # старый пароль всё ещё валиден
    still = api_client.post("/api/v1/auth/login", json={"email": email, "password": "strongpass123"})
    assert still.status_code == 200, still.text


def test_password_change_too_short(api_client: TestClient):
    """Слишком короткий новый пароль → 422 (валидация схемы)."""
    email = "change-short@example.com"
    token = _register_and_login(api_client, email)

    resp = api_client.post(
        "/api/v1/auth/password-change",
        headers={"Cookie": f"{COOKIE_NAME}={token}"},
        json={"old_password": "strongpass123", "new_password": "123"},
    )
    assert resp.status_code == 422, resp.text


def test_password_change_requires_auth(api_client: TestClient):
    """Без авторизации → 401."""
    resp = api_client.post(
        "/api/v1/auth/password-change",
        cookies={},
        json={"old_password": "strongpass123", "new_password": "brandnew456"},
    )
    assert resp.status_code == 401, resp.text
