"""Тесты соц-входа (OAuth): гейтинг провайдеров, подпись Telegram, find-or-create."""
import asyncio
import hashlib
import hmac
import time

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base
from app.models import User
from app.services import oauth


def _run(coro):
    return asyncio.run(coro)


def test_provider_enabled_gating(monkeypatch):
    monkeypatch.setattr(settings, "yandex_client_id", "")
    monkeypatch.setattr(settings, "yandex_client_secret", "")
    monkeypatch.setattr(settings, "oauth_redirect_base", "")
    assert oauth.provider_enabled("yandex") is False

    monkeypatch.setattr(settings, "yandex_client_id", "cid")
    monkeypatch.setattr(settings, "yandex_client_secret", "sec")
    monkeypatch.setattr(settings, "oauth_redirect_base", "https://api.example.com")
    assert oauth.provider_enabled("yandex") is True

    monkeypatch.setattr(settings, "telegram_bot_token", "")
    assert oauth.provider_enabled("telegram") is False
    monkeypatch.setattr(settings, "telegram_bot_token", "123:ABC")
    assert oauth.provider_enabled("telegram") is True

    assert oauth.provider_enabled("unknown") is False


def test_build_authorize_url(monkeypatch):
    monkeypatch.setattr(settings, "yandex_client_id", "cid")
    monkeypatch.setattr(settings, "yandex_client_secret", "sec")
    monkeypatch.setattr(settings, "oauth_redirect_base", "https://api.example.com")
    url = oauth.build_authorize_url("yandex", "st8")
    assert url.startswith("https://oauth.yandex.ru/authorize?")
    assert "client_id=cid" in url
    assert "state=st8" in url
    assert "redirect_uri=" in url


def test_verify_telegram_auth(monkeypatch):
    monkeypatch.setattr(settings, "telegram_bot_token", "123456:TESTTOKEN")
    secret = hashlib.sha256(b"123456:TESTTOKEN").digest()

    def _sign(payload):
        check = "\n".join(sorted(f"{k}={v}" for k, v in payload.items()))
        return hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()

    # Свежая подпись (auth_date "сейчас") проходит.
    data = {"id": "777", "first_name": "Иван", "username": "ivan",
            "auth_date": str(int(time.time()))}
    good_hash = _sign(data)
    assert oauth.verify_telegram_auth({**data, "hash": good_hash}) is True
    assert oauth.verify_telegram_auth({**data, "hash": "deadbeef"}) is False
    assert oauth.verify_telegram_auth({**data}) is False  # нет hash

    # Устаревшая подпись (auth_date старше суток) отклоняется, даже с верным hash.
    stale = {"id": "777", "first_name": "Иван", "username": "ivan",
             "auth_date": str(int(time.time()) - 48 * 3600)}
    assert oauth.verify_telegram_auth({**stale, "hash": _sign(stale)}) is False


async def _with_session(fn):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    try:
        async with maker() as session:
            await fn(session)
    finally:
        await engine.dispose()


def test_find_or_create_by_email_and_link():
    async def scenario(session):
        u1 = await oauth.find_or_create_oauth_user(
            session, provider="yandex", sub="A1", email="user@example.com",
            name="U", email_verified=True,
        )
        assert u1.id is not None
        assert u1.email == "user@example.com"
        assert u1.email_verified is True
        assert u1.oauth_provider == "yandex"
        # повторный вход тем же ПОДТВЕРЖДЁННЫМ email -> тот же пользователь
        u2 = await oauth.find_or_create_oauth_user(
            session, provider="google", sub="G2", email="user@example.com",
            email_verified=True,
        )
        assert u2.id == u1.id
    _run(_with_session(scenario))


def test_find_or_create_without_email():
    async def scenario(session):
        u = await oauth.find_or_create_oauth_user(
            session, provider="telegram", sub="555", email=None, name="Tg"
        )
        assert u.id is not None
        assert u.oauth_provider == "telegram"
        assert u.oauth_id == "555"
        # повтор по (provider, sub) -> тот же
        u2 = await oauth.find_or_create_oauth_user(
            session, provider="telegram", sub="555", email=None
        )
        assert u2.id == u.id
    _run(_with_session(scenario))


def test_find_or_create_unverified_email_does_not_link():
    """Непроверенный провайдером email не должен линковаться к чужому аккаунту
    (security-ревью 2026-07-10, находка #3)."""
    async def scenario(session):
        victim = await oauth.find_or_create_oauth_user(
            session, provider="yandex", sub="V1", email="victim@example.com",
            email_verified=True,
        )
        # Атакующий заводит у другого провайдера аккаунт с тем же, но НЕ
        # подтверждённым email — линковки к жертве быть не должно.
        attacker = await oauth.find_or_create_oauth_user(
            session, provider="google", sub="ATT", email="victim@example.com",
            email_verified=False,
        )
        assert attacker.id != victim.id
        assert attacker.email != "victim@example.com"
        assert attacker.email_verified is False
        assert attacker.oauth_provider == "google"
    _run(_with_session(scenario))
