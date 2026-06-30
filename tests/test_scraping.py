"""Тесты единого слоя загрузки HTML (app/services/scraping.py).

Проверяем маршрутизацию (ScrapingBee при ключе / прямой httpx без него / фолбэк
при сбое скрейпера) и формирование параметров запроса к ScrapingBee. Сеть не
дёргается: внутренние функции и httpx-клиент замоканы.
"""

import asyncio

import pytest

import app.services.scraping as scraping
from app.config import settings


def test_direct_when_no_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "scrapingbee_api_key", "", raising=False)

    async def fake_bee(*a, **k):
        return "BEE"

    async def fake_direct(*a, **k):
        return "DIRECT"

    monkeypatch.setattr(scraping, "_fetch_via_scrapingbee", fake_bee)
    monkeypatch.setattr(scraping, "_fetch_direct", fake_direct)

    assert asyncio.run(scraping.fetch_html("https://x")) == "DIRECT"


def test_uses_scrapingbee_when_key(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "scrapingbee_api_key", "sb-key", raising=False)

    async def fake_bee(*a, **k):
        return "BEE"

    async def fake_direct(*a, **k):
        return "DIRECT"

    monkeypatch.setattr(scraping, "_fetch_via_scrapingbee", fake_bee)
    monkeypatch.setattr(scraping, "_fetch_direct", fake_direct)

    assert asyncio.run(scraping.fetch_html("https://x")) == "BEE"


def test_fallback_to_direct_when_bee_fails(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "scrapingbee_api_key", "sb-key", raising=False)

    async def fake_bee(*a, **k):
        return None  # скрейпер не ответил

    async def fake_direct(*a, **k):
        return "DIRECT"

    monkeypatch.setattr(scraping, "_fetch_via_scrapingbee", fake_bee)
    monkeypatch.setattr(scraping, "_fetch_direct", fake_direct)

    assert asyncio.run(scraping.fetch_html("https://x")) == "DIRECT"


def test_scrapingbee_params_built_correctly(monkeypatch: pytest.MonkeyPatch):
    """Реальный _fetch_via_scrapingbee: проверяем параметры запроса к API."""
    monkeypatch.setattr(settings, "scrapingbee_api_key", "sb-key", raising=False)
    monkeypatch.setattr(settings, "scrapingbee_premium_proxy", True, raising=False)
    monkeypatch.setattr(settings, "scrapingbee_country_code", "ru", raising=False)
    monkeypatch.setattr(settings, "scrapingbee_render_js", False, raising=False)

    captured = {}

    class _Resp:
        status_code = 200
        text = "<html>ok</html>"

    class _FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            captured["url"] = url
            captured["params"] = params
            return _Resp()

    monkeypatch.setattr(scraping.httpx, "AsyncClient", _FakeClient)

    html = asyncio.run(
        scraping._fetch_via_scrapingbee(
            "https://www.avito.ru/x",
            timeout=10.0,
            render_js=None,
            premium_proxy=None,
            country_code=None,
        )
    )
    assert html == "<html>ok</html>"
    assert captured["url"] == scraping.SCRAPINGBEE_ENDPOINT
    p = captured["params"]
    assert p["api_key"] == "sb-key"
    assert p["url"] == "https://www.avito.ru/x"
    assert p["render_js"] == "false"
    assert p["premium_proxy"] == "true"
    assert p["country_code"] == "ru"
