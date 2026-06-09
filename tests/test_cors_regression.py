"""Регрессионные тесты CORS-конфигурации AutoRewier.

Проверяет, что сервер корректно обрабатывает preflight OPTIONS-запросы
и проставляет заголовок Access-Control-Allow-Origin для разрешённых origins.

Тесты используют синхронный TestClient без внешних запросов.
"""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.database as database
    import app.services.inspections as inspections
    from app.config import settings

    db_file = tmp_path / "cors_regression.db"
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

    with TestClient(app, raise_server_exceptions=True) as client:
        yield client

    asyncio.run(test_engine.dispose())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_cors_preflight_from_vite_dev(api_client: TestClient):
    """OPTIONS-запрос с Origin http://localhost:5173 должен получить 200
    и корректные CORS-заголовки (Vite dev-сервер по умолчанию)."""
    vite_origin = "http://localhost:5173"

    resp = api_client.options(
        "/api/v1/health",
        headers={
            "Origin": vite_origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    # FastAPI/Starlette отвечает 200 на preflight для разрешённых origins
    assert resp.status_code == 200, (
        f"Ожидался 200, получен {resp.status_code}. "
        "Проверьте список allow_origins в CORSMiddleware."
    )

    allow_origin = resp.headers.get("access-control-allow-origin", "")
    assert allow_origin == vite_origin, (
        f"Access-Control-Allow-Origin должен быть '{vite_origin}', получен '{allow_origin}'"
    )

    # Preflight должен разрешать хотя бы GET/POST/OPTIONS
    allow_methods = resp.headers.get("access-control-allow-methods", "").upper()
    assert any(m in allow_methods for m in ("GET", "POST", "*")), (
        f"access-control-allow-methods не содержит GET/POST: '{allow_methods}'"
    )


def test_cors_actual_request(api_client: TestClient):
    """GET /api/v1/health с заголовком Origin должен вернуть
    Access-Control-Allow-Origin в ответе."""
    vite_origin = "http://localhost:5173"

    resp = api_client.get(
        "/api/v1/health",
        headers={"Origin": vite_origin},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "ok"

    allow_origin = resp.headers.get("access-control-allow-origin", "")
    assert allow_origin, (
        "Заголовок Access-Control-Allow-Origin отсутствует в ответе на запрос с Origin. "
        "CORS-middleware не добавил его — проверьте allow_origins."
    )
    assert allow_origin in (vite_origin, "*"), (
        f"Неожиданное значение Access-Control-Allow-Origin: '{allow_origin}'"
    )
