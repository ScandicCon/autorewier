"""Регрессионные тесты ключевых API-эндпоинтов AutoRewier.

Все тесты используют синхронный TestClient (как в существующих e2e-тестах),
реальную in-memory SQLite БД и не делают внешних сетевых запросов.
"""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.services.auth import COOKIE_NAME


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.database as database
    import app.services.inspections as inspections
    from app.config import settings

    db_file = tmp_path / "regression.db"
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register(client: TestClient, email: str, password: str = "strongpass123") -> str:
    """Регистрирует пользователя, возвращает сессионный cookie."""
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password, "password_confirm": password})
    assert resp.status_code == 200, resp.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    session_token = login.cookies.get(COOKIE_NAME)
    assert session_token, "Ожидался set-cookie после регистрации"
    return session_token


def _auth_headers(session_token: str) -> dict:
    return {"Cookie": f"{COOKIE_NAME}={session_token}"}


def _inspection_payload() -> dict:
    return {
        "vehicle": {
            "brand": "Toyota",
            "model": "Corolla",
            "year": 2016,
            "mileage_km": 150000,
            "price_rub": 900000,
        },
        "pre_defects": "скрип в подвеске",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_health_endpoint(api_client: TestClient):
    """GET /api/v1/health должен вернуть 200 с {"status": "ok"}."""
    resp = api_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


def test_me_requires_auth(api_client: TestClient):
    """GET /api/v1/me без токена должен вернуть 401."""
    resp = api_client.get("/api/v1/me")
    assert resp.status_code == 401


def test_inspections_requires_auth(api_client: TestClient):
    """GET /api/v1/inspections без токена должен вернуть 401."""
    resp = api_client.get("/api/v1/inspections")
    assert resp.status_code == 401


def test_create_inspection_basic(api_client: TestClient):
    """POST /api/v1/inspections создаёт инспекцию и возвращает id."""
    token = _register(api_client, "create-basic@example.com")
    resp = api_client.post(
        "/api/v1/inspections",
        json=_inspection_payload(),
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "id" in data
    assert isinstance(data["id"], int)


def test_inspection_response_schema(api_client: TestClient):
    """Ответ на создание инспекции содержит обязательные поля контракта."""
    token = _register(api_client, "schema-check@example.com")
    resp = api_client.post(
        "/api/v1/inspections",
        json=_inspection_payload(),
        headers=_auth_headers(token),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    required_fields = {"id", "stage", "created_at"}
    missing = required_fields - data.keys()
    assert not missing, f"Отсутствуют поля в ответе: {missing}"

    assert data["stage"] in {"pre_inspection", "post_inspection"}
    assert data["created_at"]


def test_parse_listing_requires_auth(api_client: TestClient):
    """POST /api/v1/parse-listing без токена должен вернуть 401."""
    resp = api_client.post(
        "/api/v1/parse-listing",
        json={"url": "https://www.avito.ru/items/42"},
    )
    assert resp.status_code == 401


def test_vin_check_requires_auth(api_client: TestClient):
    """POST /api/v1/vin/check/async без токена должен вернуть 401."""
    resp = api_client.post(
        "/api/v1/vin/check/async",
        json={"vin": "XTA12345678901234"},
    )
    assert resp.status_code == 401


def test_admin_health_requires_token(api_client: TestClient, monkeypatch: pytest.MonkeyPatch):
    """GET /api/v1/admin/health без X-Admin-Token должен вернуть 403."""
    from app.config import settings

    monkeypatch.setattr(settings, "admin_api_token", "secret-token")

    resp = api_client.get("/api/v1/admin/health")
    assert resp.status_code == 403
