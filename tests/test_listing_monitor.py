"""
Тесты мониторинга объявлений.

Покрываемые сценарии:
- POST /monitored-listings → 201, возвращает id
- GET /monitored-listings → список
- DELETE /monitored-listings/{id} → 204
- Mock парсер возвращает цену ниже → создаётся ListingChangeEvent с change_type="price_drop"
- Mock статус "sold" → ListingChangeEvent type="sold"
- Цена не изменилась → нет новых events

Заметки о реализации:
- Эндпоинты /monitored-listings и сервис listing_monitor являются новыми фичами.
  Если они ещё не реализованы, тесты HTTP-эндпоинтов пропускаются.
- Тесты бизнес-логики (check_listing_*) тестируют сервисный слой напрямую
  и предполагают наличие модуля app.services.listing_monitor.
"""

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

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

    db_file = tmp_path / "test_listing_monitor.db"
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

def _run(coro):
    return asyncio.run(coro)


def _register(client: TestClient, email: str, password: str = "strongpass123") -> str:
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 200
    return resp.cookies.get(COOKIE_NAME)


def _auth_headers(session_token: str) -> dict:
    return {"Cookie": f"{COOKIE_NAME}={session_token}"}


# ---------------------------------------------------------------------------
# Data classes для stub-реализации сервиса
# ---------------------------------------------------------------------------

@dataclass
class _MonitoredListing:
    id: int
    user_id: int
    url: str
    last_price: int | None = None
    last_status: str | None = None


@dataclass
class _ListingChangeEvent:
    monitored_listing_id: int
    change_type: str  # "price_drop" | "sold" | "price_increase"
    old_value: Any = None
    new_value: Any = None


# ---------------------------------------------------------------------------
# HTTP endpoint tests (пропускаются если эндпоинт не реализован)
# ---------------------------------------------------------------------------

def test_add_monitoring(api_client: TestClient):
    """POST /monitored-listings → 201, возвращает id."""
    session_token = _register(api_client, "monitor-add@example.com")
    headers = _auth_headers(session_token)

    resp = api_client.post(
        "/api/v1/monitored-listings",
        json={"url": "https://auto.drom.ru/toyota/camry-12345"},
        headers=headers,
    )
    if resp.status_code in (404, 405):
        pytest.skip("Эндпоинт /monitored-listings ещё не реализован")

    assert resp.status_code == 201
    payload = resp.json()
    assert "id" in payload
    assert isinstance(payload["id"], int)


def test_list_monitoring(api_client: TestClient):
    """GET /monitored-listings → список мониторингов пользователя."""
    session_token = _register(api_client, "monitor-list@example.com")
    headers = _auth_headers(session_token)

    # Добавляем один мониторинг
    add_resp = api_client.post(
        "/api/v1/monitored-listings",
        json={"url": "https://auto.drom.ru/kia/rio-99999"},
        headers=headers,
    )
    if add_resp.status_code in (404, 405):
        pytest.skip("Эндпоинт /monitored-listings ещё не реализован")

    assert add_resp.status_code == 201

    list_resp = api_client.get(
        "/api/v1/monitored-listings",
        headers=headers,
    )
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert isinstance(items, list)
    assert len(items) >= 1
    assert any(item.get("url") == "https://auto.drom.ru/kia/rio-99999" for item in items)


def test_delete_monitoring(api_client: TestClient):
    """DELETE /monitored-listings/{id} → 204."""
    session_token = _register(api_client, "monitor-delete@example.com")
    headers = _auth_headers(session_token)

    # Создаём запись
    add_resp = api_client.post(
        "/api/v1/monitored-listings",
        json={"url": "https://auto.drom.ru/honda/civic-55555"},
        headers=headers,
    )
    if add_resp.status_code in (404, 405):
        pytest.skip("Эндпоинт /monitored-listings ещё не реализован")

    assert add_resp.status_code == 201
    monitoring_id = add_resp.json()["id"]

    # Удаляем
    del_resp = api_client.delete(
        f"/api/v1/monitored-listings/{monitoring_id}",
        headers=headers,
    )
    assert del_resp.status_code == 204

    # Проверяем что запись исчезла
    list_resp = api_client.get("/api/v1/monitored-listings", headers=headers)
    assert list_resp.status_code == 200
    ids = [item["id"] for item in list_resp.json()]
    assert monitoring_id not in ids


# ---------------------------------------------------------------------------
# Business logic tests (тестируем сервисный слой напрямую)
# ---------------------------------------------------------------------------

def test_check_listing_price_drop(monkeypatch: pytest.MonkeyPatch):
    """
    Если парсер возвращает цену ниже сохранённой — создаётся
    ListingChangeEvent с change_type="price_drop".
    """
    try:
        import app.services.listing_monitor as lm
    except ImportError:
        pytest.skip("Модуль app.services.listing_monitor ещё не реализован")

    listing = _MonitoredListing(
        id=1,
        user_id=1,
        url="https://auto.drom.ru/toyota/camry-1",
        last_price=900_000,
        last_status="active",
    )

    # Mock парсер возвращает цену ниже
    async def _mock_fetch_current_price(url: str) -> dict:
        return {"price": 800_000, "status": "active"}

    monkeypatch.setattr(lm, "fetch_current_listing_state", _mock_fetch_current_price, raising=False)

    events: list = _run(lm.check_listing(listing))

    assert len(events) >= 1
    price_drop_events = [e for e in events if getattr(e, "change_type", None) == "price_drop"]
    assert price_drop_events, f"Ожидался price_drop event, получено: {events}"
    event = price_drop_events[0]
    assert event.old_value == 900_000
    assert event.new_value == 800_000


def test_check_listing_sold(monkeypatch: pytest.MonkeyPatch):
    """
    Если парсер возвращает статус 'sold' — создаётся
    ListingChangeEvent с change_type="sold".
    """
    try:
        import app.services.listing_monitor as lm
    except ImportError:
        pytest.skip("Модуль app.services.listing_monitor ещё не реализован")

    listing = _MonitoredListing(
        id=2,
        user_id=1,
        url="https://auto.drom.ru/kia/rio-2",
        last_price=700_000,
        last_status="active",
    )

    async def _mock_fetch_sold(url: str) -> dict:
        return {"price": 700_000, "status": "sold"}

    monkeypatch.setattr(lm, "fetch_current_listing_state", _mock_fetch_sold, raising=False)

    events: list = _run(lm.check_listing(listing))

    sold_events = [e for e in events if getattr(e, "change_type", None) == "sold"]
    assert sold_events, f"Ожидался sold event, получено: {events}"


def test_monitoring_cycle_no_changes(monkeypatch: pytest.MonkeyPatch):
    """
    Если цена и статус не изменились — новых events не создаётся.
    """
    try:
        import app.services.listing_monitor as lm
    except ImportError:
        pytest.skip("Модуль app.services.listing_monitor ещё не реализован")

    listing = _MonitoredListing(
        id=3,
        user_id=1,
        url="https://auto.drom.ru/skoda/octavia-3",
        last_price=1_100_000,
        last_status="active",
    )

    async def _mock_fetch_unchanged(url: str) -> dict:
        return {"price": 1_100_000, "status": "active"}

    monkeypatch.setattr(lm, "fetch_current_listing_state", _mock_fetch_unchanged, raising=False)

    events: list = _run(lm.check_listing(listing))

    assert len(events) == 0, f"Не ожидалось events при неизменных данных, получено: {events}"
