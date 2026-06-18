"""Вход через соцсети (OAuth) + Telegram Login.

Каждый провайдер активен только при заданных client_id/secret (мягкая деградация).
Поток redirect-провайдеров (yandex/vk/google):
  /start -> authorize_url провайдера -> /callback?code -> обмен кода на профиль
  -> find_or_create_user -> JWT -> redirect на фронт.
Telegram — отдельно, через подпись данных виджета (verify_telegram_auth).
"""
from __future__ import annotations

import hashlib
import hmac
from urllib.parse import urlencode

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import User
from app.services.auth import issue_session

REDIRECT_PROVIDERS = ("yandex", "vk", "google")


def _client(provider: str) -> tuple[str, str]:
    cid = getattr(settings, f"{provider}_client_id", "").strip()
    secret = getattr(settings, f"{provider}_client_secret", "").strip()
    return cid, secret


def provider_enabled(provider: str) -> bool:
    if provider == "telegram":
        return bool(settings.telegram_bot_token.strip())
    if provider not in REDIRECT_PROVIDERS:
        return False
    cid, secret = _client(provider)
    return bool(cid and secret and settings.oauth_redirect_base.strip())


def _redirect_uri(provider: str) -> str:
    base = settings.oauth_redirect_base.strip().rstrip("/")
    return f"{base}/api/v1/auth/oauth/{provider}/callback"


def success_redirect() -> str:
    if settings.oauth_success_redirect.strip():
        return settings.oauth_success_redirect.strip()
    return settings.web_base_url.rstrip("/") + "/oauth-callback"


def build_authorize_url(provider: str, state: str) -> str:
    cid, _ = _client(provider)
    redirect_uri = _redirect_uri(provider)
    if provider == "yandex":
        params = {
            "response_type": "code",
            "client_id": cid,
            "redirect_uri": redirect_uri,
            "state": state,
        }
        return "https://oauth.yandex.ru/authorize?" + urlencode(params)
    if provider == "google":
        params = {
            "response_type": "code",
            "client_id": cid,
            "redirect_uri": redirect_uri,
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
        return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)
    if provider == "vk":
        params = {
            "client_id": cid,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "email",
            "v": "5.131",
            "state": state,
        }
        return "https://oauth.vk.com/authorize?" + urlencode(params)
    raise ValueError(f"Unknown provider: {provider}")


async def exchange_code(provider: str, code: str) -> dict:
    """Меняет authorization code на профиль: {provider, sub, email, name}."""
    cid, secret = _client(provider)
    redirect_uri = _redirect_uri(provider)
    async with httpx.AsyncClient(timeout=20.0) as client:
        if provider == "yandex":
            tok = await client.post(
                "https://oauth.yandex.ru/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": cid,
                    "client_secret": secret,
                },
            )
            tok.raise_for_status()
            access = tok.json()["access_token"]
            prof = await client.get(
                "https://login.yandex.ru/info",
                params={"format": "json"},
                headers={"Authorization": f"OAuth {access}"},
            )
            prof.raise_for_status()
            data = prof.json()
            return {
                "provider": "yandex",
                "sub": str(data.get("id")),
                "email": (data.get("default_email") or "").lower() or None,
                "name": data.get("real_name") or data.get("display_name") or data.get("login"),
            }
        if provider == "google":
            tok = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "client_id": cid,
                    "client_secret": secret,
                    "redirect_uri": redirect_uri,
                },
            )
            tok.raise_for_status()
            access = tok.json()["access_token"]
            prof = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access}"},
            )
            prof.raise_for_status()
            data = prof.json()
            return {
                "provider": "google",
                "sub": str(data.get("id")),
                "email": (data.get("email") or "").lower() or None,
                "name": data.get("name"),
            }
        if provider == "vk":
            tok = await client.get(
                "https://oauth.vk.com/access_token",
                params={
                    "client_id": cid,
                    "client_secret": secret,
                    "redirect_uri": redirect_uri,
                    "code": code,
                },
            )
            tok.raise_for_status()
            data = tok.json()
            return {
                "provider": "vk",
                "sub": str(data.get("user_id")),
                "email": (data.get("email") or "").lower() or None,
                "name": None,
            }
    raise ValueError(f"Unknown provider: {provider}")


def verify_telegram_auth(data: dict) -> bool:
    """Проверяет подпись данных Telegram Login Widget по токену бота."""
    token = settings.telegram_bot_token.strip()
    if not token:
        return False
    received_hash = data.get("hash")
    if not received_hash:
        return False
    pairs = sorted(f"{k}={v}" for k, v in data.items() if k != "hash")
    data_check_string = "\n".join(pairs)
    secret_key = hashlib.sha256(token.encode()).digest()
    calc = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(calc, str(received_hash))


async def find_or_create_oauth_user(
    session: AsyncSession,
    *,
    provider: str,
    sub: str,
    email: str | None,
    name: str | None = None,
) -> User:
    """Находит пользователя по email или по (provider, sub), иначе создаёт нового.
    Соц-вход выдаёт уже подтверждённый аккаунт (email_verified=True)."""
    user: User | None = None

    if email:
        res = await session.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()

    if user is None:
        res = await session.execute(
            select(User).where(User.oauth_provider == provider, User.oauth_id == str(sub))
        )
        user = res.scalar_one_or_none()

    if user is None:
        user = User(
            email=email or f"{provider}_{sub}@oauth.local",
            email_verified=True,
            oauth_provider=provider,
            oauth_id=str(sub),
        )
        session.add(user)
    else:
        # связываем соц-аккаунт с существующим пользователем
        if not user.oauth_provider:
            user.oauth_provider = provider
            user.oauth_id = str(sub)
        if email and not user.email_verified:
            user.email_verified = True

    issue_session(user)
    await session.commit()
    await session.refresh(user)
    return user
