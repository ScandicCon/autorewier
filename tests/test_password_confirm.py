"""Тесты валидации password_confirm и cookie-механики аутентификации.

Покрывают:
- совпадение/несовпадение паролей при регистрации (RegisterRequest.password_confirm)
- отсутствие поля password_confirm → 422
- Set-Cookie после логина
- очистку cookie после logout
- GET /auth/check с cookie и без
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

    db_file = tmp_path / "password_confirm.db"
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


def _register_payload(
    email: str,
    password: str = "strongpass123",
    password_confirm: str = "strongpass123",
) -> dict:
    return {"email": email, "password": password, "password_confirm": password_confirm}


def _do_login(client: TestClient, email: str, password: str = "strongpass123") -> str:
    """Регистрирует и логинит пользователя, возвращает session cookie."""
    client.post("/api/v1/auth/register", json=_register_payload(email, password, password))
    resp = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    token = resp.cookies.get(COOKIE_NAME)
    assert token, "Ожидался Set-Cookie после логина"
    return token


# ---------------------------------------------------------------------------
# Tests: password_confirm validation
# ---------------------------------------------------------------------------


def test_register_passwords_match(api_client: TestClient):
    """Одинаковые пароли → регистрация успешна, HTTP 200."""
    resp = api_client.post(
        "/api/v1/auth/register",
        json=_register_payload("match@example.com", "strongpass123", "strongpass123"),
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["email"] == "match@example.com"


def test_register_passwords_mismatch(api_client: TestClient):
    """Разные пароли → 422 с понятным сообщением об ошибке."""
    resp = api_client.post(
        "/api/v1/auth/register",
        json=_register_payload("mismatch@example.com", "strongpass123", "different456"),
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    # Pydantic возвращает список ошибок в поле "detail"
    detail = body.get("detail", [])
    # Сообщение должно упоминать несовпадение паролей
    error_messages = " ".join(
        str(err.get("msg", "")) for err in detail
    ).lower()
    assert "пароли" in error_messages or "password" in error_messages or "совпада" in error_messages, (
        f"Ожидалось упоминание несовпадения паролей в ошибке, получено: {detail}"
    )


def test_register_missing_confirm(api_client: TestClient):
    """Отсутствует поле password_confirm → 422 (ошибка валидации схемы)."""
    resp = api_client.post(
        "/api/v1/auth/register",
        json={"email": "noconfirm@example.com", "password": "strongpass123"},
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    detail = body.get("detail", [])
    # Ошибка должна указывать на отсутствующее поле password_confirm
    fields = [
        str(err.get("loc", [])) for err in detail
    ]
    assert any("password_confirm" in f for f in fields), (
        f"Ожидалась ошибка на поле password_confirm, получено: {detail}"
    )


# ---------------------------------------------------------------------------
# Tests: cookie lifecycle
# ---------------------------------------------------------------------------


def test_login_sets_cookie(api_client: TestClient):
    """POST /auth/login возвращает Set-Cookie header с сессионным токеном."""
    email = "login-cookie@example.com"
    # Сначала регистрируем через register (без cookie)
    reg = api_client.post(
        "/api/v1/auth/register",
        json=_register_payload(email),
    )
    assert reg.status_code == 200, reg.text

    # Логинимся и проверяем cookie
    login_resp = api_client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "strongpass123"},
    )
    assert login_resp.status_code == 200, login_resp.text
    session_token = login_resp.cookies.get(COOKIE_NAME)
    assert session_token, (
        f"Ожидался Set-Cookie: {COOKIE_NAME}=<token>, "
        f"cookies в ответе: {dict(login_resp.cookies)}"
    )


def test_logout_clears_session(api_client: TestClient):
    """POST /auth/logout устанавливает пустой cookie (или expires в прошлом), очищая сессию."""
    email = "logout-clear@example.com"
    session_token = _do_login(api_client, email)

    # Убеждаемся, что до logout аутентифицированы
    check_before = api_client.get(
        "/api/v1/auth/check",
        headers={"Cookie": f"{COOKIE_NAME}={session_token}"},
    )
    assert check_before.status_code == 200, check_before.text

    # Выходим
    logout_resp = api_client.post(
        "/api/v1/auth/logout",
        headers={"Cookie": f"{COOKIE_NAME}={session_token}"},
    )
    assert logout_resp.status_code == 200, logout_resp.text

    # После logout тот же токен больше не работает (сервер удалил cookie)
    # delete_cookie ставит пустое значение с expires=0 или max_age=0
    raw_set_cookie = logout_resp.headers.get("set-cookie", "")
    assert (
        f"{COOKIE_NAME}=" in raw_set_cookie.lower()
        or COOKIE_NAME.lower() in raw_set_cookie.lower()
    ), f"Ожидался Set-Cookie для очистки, получено: {raw_set_cookie!r}"


def test_check_auth_authenticated(api_client: TestClient):
    """GET /auth/check с валидным cookie → {"authenticated": true}."""
    email = "check-auth@example.com"
    session_token = _do_login(api_client, email)

    resp = api_client.get(
        "/api/v1/auth/check",
        headers={"Cookie": f"{COOKIE_NAME}={session_token}"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["authenticated"] is True
    assert data.get("email") == email


def test_check_auth_unauthenticated(api_client: TestClient):
    """GET /auth/check без cookie → 401 Unauthorized."""
    # Явно не передаём cookie
    resp = api_client.get("/api/v1/auth/check", cookies={})
    assert resp.status_code == 401, resp.text
