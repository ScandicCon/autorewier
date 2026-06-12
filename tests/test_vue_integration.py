"""Тесты интеграции Vue SPA с API AutoRewier.

Проверяет:
- что фронтенд-артефакт (frontend/dist) отдаётся по /app/ (skip если не собран)
- контракт JSON ответа GET /api/v1/health
- схему ответа POST /api/v1/inspections (поля id, stage, created_at)
- полный auth-flow: регистрация → вход → /api/v1/me возвращает email

Все тесты используют синхронный TestClient без внешних сетевых запросов.
"""

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import BASE_DIR
from app.main import app
from app.services.auth import COOKIE_NAME

FRONTEND_DIST = BASE_DIR / "frontend" / "dist"


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def api_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import app.database as database
    import app.services.inspections as inspections
    from app.config import settings

    db_file = tmp_path / "vue_integration.db"
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
# Helpers
# ---------------------------------------------------------------------------


def _register(client: TestClient, email: str, password: str = "strongpass123") -> tuple[str, str]:
    """Регистрирует пользователя. Возвращает (session_cookie, bearer_token)."""
    resp = client.post("/api/v1/auth/register", json={"email": email, "password": password, "password_confirm": password})
    assert resp.status_code == 200, resp.text
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    session_token = login.cookies.get(COOKIE_NAME)
    assert session_token, "Ожидался set-cookie после входа"
    bearer = login.json().get("token", "")
    return session_token, bearer


def _inspection_payload() -> dict:
    return {
        "vehicle": {
            "brand": "Toyota",
            "model": "Corolla",
            "year": 2018,
            "mileage_km": 80000,
            "price_rub": 1100000,
        },
        "pre_defects": "небольшой скол на бампере",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_spa_served_at_app(api_client: TestClient):
    """GET /app/ должен вернуть 200 с HTML-содержимым Vue SPA.

    Пропускается автоматически если frontend/dist не собран.
    """
    if not (FRONTEND_DIST / "index.html").exists():
        pytest.skip("frontend/dist/index.html не найден — фронтенд не собран")

    resp = api_client.get("/app/", follow_redirects=True)
    assert resp.status_code == 200, resp.text
    content_type = resp.headers.get("content-type", "")
    assert "text/html" in content_type, (
        f"Ожидался content-type text/html, получен '{content_type}'"
    )


def test_api_health_json(api_client: TestClient):
    """GET /api/v1/health должен вернуть {"status": "ok"} — контракт для Vue."""
    resp = api_client.get("/api/v1/health")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data.get("status") == "ok", (
        f"Поле 'status' должно быть 'ok', получено: {data}"
    )


def test_inspection_api_contract(api_client: TestClient):
    """POST /api/v1/inspections должен вернуть объект с полями id, stage, created_at.

    Эти поля используются Vue-компонентами через inspectionApi.js.
    """
    session_token, _ = _register(api_client, "contract-check@example.com")

    resp = api_client.post(
        "/api/v1/inspections",
        json=_inspection_payload(),
        headers={"Cookie": f"{COOKIE_NAME}={session_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()

    for field in ("id", "stage", "created_at"):
        assert field in data, (
            f"Поле '{field}' отсутствует в ответе инспекции. "
            f"Vue-компонент ожидает его согласно inspectionApi.js."
        )

    assert isinstance(data["id"], int), "id должен быть целым числом"
    assert data["stage"] in {"pre_inspection", "post_inspection"}, (
        f"Неожиданное значение stage: '{data['stage']}'"
    )
    assert data["created_at"], "created_at не должен быть пустым"


def test_auth_flow_register_login(api_client: TestClient):
    """Полный auth-flow: регистрация → вход → GET /api/v1/me возвращает email.

    Воспроизводит последовательность вызовов из Vue-приложения
    (useAuth / inspectionApi.fetchCurrentUser).
    """
    email = "vue-auth-flow@example.com"
    password = "strongpass123"

    # 1. Регистрация (не логинит автоматически — нужно войти отдельно)
    register_resp = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "password_confirm": password},
    )
    assert register_resp.status_code == 200, register_resp.text

    # 2. Первый вход — выдаётся сессионный cookie
    login_resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert login_resp.status_code == 200, login_resp.text
    first_cookie = login_resp.cookies.get(COOKIE_NAME)
    assert first_cookie, "После входа ожидался сессионный cookie"

    # 3. /api/v1/me с cookie возвращает email (fetchCurrentUser)
    me_resp = api_client.get(
        "/api/v1/me",
        headers={"Cookie": f"{COOKIE_NAME}={first_cookie}"},
    )
    assert me_resp.status_code == 200, me_resp.text
    me_data = me_resp.json()
    assert me_data.get("email") == email, (
        f"Ожидался email '{email}', получено: {me_data.get('email')}"
    )

    # 4. Повторный вход ротирует токен — старый cookie становится недействителен
    relogin_resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
    )
    assert relogin_resp.status_code == 200, relogin_resp.text
    rotated_cookie = relogin_resp.cookies.get(COOKIE_NAME)
    assert rotated_cookie and rotated_cookie != first_cookie

    old_cookie_resp = api_client.get(
        "/api/v1/me",
        headers={"Cookie": f"{COOKIE_NAME}={first_cookie}"},
    )
    assert old_cookie_resp.status_code == 401, (
        "Старый сессионный token должен быть инвалидирован после повторного входа"
    )
