"""E2E гостевого режима: проверка авто без регистрации.

Флоу: POST /auth/guest -> сессионная кука -> одна бесплатная проверка ->
на второй отказ (402) -> регистрация апгрейдит гостя, история сохраняется.
"""
import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models import User
from app.services.auth import COOKIE_NAME


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.database as database
    import app.services.inspections as inspections
    from app.config import settings

    db_file = tmp_path / "e2e_guest_flow.db"
    test_db_url = f"sqlite+aiosqlite:///{db_file}"
    test_engine = create_async_engine(test_db_url, echo=False)
    test_sessionmaker = async_sessionmaker(
        test_engine, class_=AsyncSession, expire_on_commit=False
    )

    monkeypatch.setattr(settings, "database_url", test_db_url)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    monkeypatch.setattr(database, "engine", test_engine)
    monkeypatch.setattr(database, "async_session", test_sessionmaker)

    async def _no_external_enrichment(
        report,
        vehicle,
        defects,
        user_preferences,
        listing_repairs,
    ):
        return report

    monkeypatch.setattr(inspections, "_enrich_report", _no_external_enrichment)

    with TestClient(app) as client:
        yield client

    asyncio.run(test_engine.dispose())


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


def _cookie_headers(session_token: str) -> dict[str, str]:
    return {"Cookie": f"{COOKIE_NAME}={session_token}"}


def _start_guest(client: TestClient) -> str:
    resp = client.post("/api/v1/auth/guest")
    assert resp.status_code == 200, resp.text
    assert resp.json()["guest"] is True
    token = resp.cookies.get(COOKIE_NAME)
    assert token
    return token


def test_guest_gets_one_free_inspection_then_blocked(api_client: TestClient):
    token = _start_guest(api_client)
    headers = _cookie_headers(token)

    me = api_client.get("/api/v1/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["is_guest"] is True

    first = api_client.post("/api/v1/inspections", json=_inspection_payload(), headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["verdict"]

    second = api_client.post("/api/v1/inspections", json=_inspection_payload(), headers=headers)
    assert second.status_code == 402
    assert "аккаунт" in second.json()["detail"].lower()


def test_guest_endpoint_reuses_existing_session(api_client: TestClient):
    token = _start_guest(api_client)
    first_id = api_client.get("/api/v1/me", headers=_cookie_headers(token)).json()["id"]

    again = api_client.post("/api/v1/auth/guest", headers=_cookie_headers(token))
    assert again.status_code == 200
    assert again.json()["id"] == first_id
    assert again.json()["guest"] is True


def test_guest_register_upgrades_account_and_keeps_history(api_client: TestClient):
    token = _start_guest(api_client)
    headers = _cookie_headers(token)

    created = api_client.post("/api/v1/inspections", json=_inspection_payload(), headers=headers)
    assert created.status_code == 200
    inspection_id = created.json()["id"]
    guest_id = api_client.get("/api/v1/me", headers=headers).json()["id"]

    email = "upgraded-guest@example.com"
    reg = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "strongpass123", "password_confirm": "strongpass123"},
        headers=headers,
    )
    assert reg.status_code == 200, reg.text
    body = reg.json()
    assert body["upgraded_from_guest"] is True
    assert body["id"] == guest_id
    new_token = reg.cookies.get(COOKIE_NAME)
    assert new_token

    me = api_client.get("/api/v1/me", headers=_cookie_headers(new_token))
    assert me.status_code == 200
    assert me.json()["email"] == email
    assert me.json()["is_guest"] is False

    history = api_client.get("/api/v1/inspections", headers=_cookie_headers(new_token))
    assert history.status_code == 200
    ids = [item["id"] for item in history.json()]
    assert inspection_id in ids


def test_registration_without_guest_session_still_works(api_client: TestClient):
    email = "plain-register@example.com"
    reg = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "strongpass123", "password_confirm": "strongpass123"},
    )
    assert reg.status_code == 200, reg.text
    assert reg.json()["upgraded_from_guest"] is False
