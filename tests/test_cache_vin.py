"""Тесты кэша и кэширования VIN-отчётов Autocode.

Без REDIS_URL кэш выключен (мягкая деградация). При попадании в кэш повторный
запрос VIN не идёт во внешний Autocode (экономия денег и нагрузки).
"""

import asyncio

import app.services.autocode as autocode
from app.config import settings
from app.services import cache


def test_cache_disabled_without_redis(monkeypatch):
    monkeypatch.setattr(settings, "redis_url", "", raising=False)
    assert cache.cache_enabled() is False
    # get отдаёт None, set не падает.
    assert asyncio.run(cache.cache_get_json("any:key")) is None
    asyncio.run(cache.cache_set_json("any:key", {"a": 1}, 60))


def test_vin_report_returns_cached_without_external_call(monkeypatch):
    # Делаем autocode «настроенным», чтобы пройти проверку autocode_enabled.
    monkeypatch.setattr(settings, "autocode_user", "u", raising=False)
    monkeypatch.setattr(settings, "autocode_password", "p", raising=False)
    monkeypatch.setattr(settings, "autocode_domain", "d", raising=False)
    monkeypatch.setattr(settings, "autocode_report_type_uid", "uid", raising=False)

    cached_report = {
        "vin": "XW8ZZZ61ZCG000000",
        "summary": "из кэша",
        "raw": {"cached": True},
    }

    async def fake_get(key):
        assert key == "vin:report:XW8ZZZ61ZCG000000"
        return cached_report

    async def fail_set(*args, **kwargs):  # не должен вызываться при кэш-хите
        raise AssertionError("cache_set не должен вызываться при попадании в кэш")

    monkeypatch.setattr(autocode, "cache_get_json", fake_get)
    monkeypatch.setattr(autocode, "cache_set_json", fail_set)

    result = asyncio.run(autocode.request_vin_report("xw8zzz61zcg000000"))
    assert result["summary"] == "из кэша"
    assert result["raw"]["cached"] is True


def test_vin_demo_mode_skips_cache(monkeypatch):
    # Autocode не настроен → демо-режим, кэш не трогаем.
    monkeypatch.setattr(settings, "autocode_user", "", raising=False)
    monkeypatch.setattr(settings, "autocode_password", "", raising=False)

    async def boom(*args, **kwargs):
        raise AssertionError("кэш не должен использоваться в демо-режиме")

    monkeypatch.setattr(autocode, "cache_get_json", boom)

    result = asyncio.run(autocode.request_vin_report("xw8zzz61zcg000000"))
    assert "демо" in result["summary"].lower()
