"""ScrapingBee как последний эшелон загрузки Avito (после Playwright и httpx).

Контракт:
- без ключа ScrapingBee поведение fetch_avito_html не меняется вовсе;
- с ключом: после блока Playwright/httpx пробуем ScrapingBee без JS-рендера,
  затем один раз с рендером; успех кэшируется и возвращает source="scrapingbee";
- неудача ScrapingBee не ломает итоговую диагностику (captcha/blocked как раньше).
"""
import asyncio

import app.services.parsers.avito_fetch as avito_fetch
from app.config import settings
from app.services.parsers.avito_fetch import AvitoFetchStatus


def _run(coro):
    return asyncio.run(coro)


def _valid_listing_html() -> str:
    return (
        '<html><body><div data-marker="item-view/title-info">Listing</div>'
        + ("x" * 8100)
        + "</body></html>"
    )


def _block_everything(monkeypatch):
    async def _fake_playwright(_url: str):
        return "<html><body>captcha gate</body></html>"

    async def _fake_httpx(_url: str):
        return None, 429, None

    monkeypatch.setattr(settings, "avito_fetch_mode", "auto")
    monkeypatch.setattr(settings, "avito_cache_enabled", False)
    monkeypatch.setattr(settings, "avito_fetch_retry_attempts", 1)
    monkeypatch.setattr(settings, "avito_browser_per_request", False)
    monkeypatch.setattr(avito_fetch, "_fetch_playwright", _fake_playwright)
    monkeypatch.setattr(avito_fetch, "_fetch_httpx", _fake_httpx)
    monkeypatch.setattr(
        avito_fetch, "_with_retry_pause", lambda attempt: asyncio.sleep(0)
    )


def test_scrapingbee_rescues_after_playwright_and_httpx_blocked(monkeypatch):
    _block_everything(monkeypatch)
    monkeypatch.setattr(settings, "scrapingbee_api_key", "test-key")
    monkeypatch.setattr(settings, "scrapingbee_render_js", False)
    calls: list[bool] = []
    valid_html = _valid_listing_html()

    async def _fake_scrapingbee(url: str, *, render_js: bool):
        calls.append(render_js)
        return valid_html

    monkeypatch.setattr(avito_fetch, "_fetch_scrapingbee", _fake_scrapingbee)

    result = _run(avito_fetch.fetch_avito_html("https://www.avito.ru/items/1234567"))

    assert result.status == AvitoFetchStatus.success
    assert result.html == valid_html
    assert result.source == "scrapingbee"
    assert calls == [False]


def test_scrapingbee_retries_with_render_js_on_invalid_html(monkeypatch):
    _block_everything(monkeypatch)
    monkeypatch.setattr(settings, "scrapingbee_api_key", "test-key")
    monkeypatch.setattr(settings, "scrapingbee_render_js", False)
    calls: list[bool] = []
    valid_html = _valid_listing_html()

    async def _fake_scrapingbee(url: str, *, render_js: bool):
        calls.append(render_js)
        if not render_js:
            return "<html>too short</html>"
        return valid_html

    monkeypatch.setattr(avito_fetch, "_fetch_scrapingbee", _fake_scrapingbee)

    result = _run(avito_fetch.fetch_avito_html("https://www.avito.ru/items/1234567"))

    assert result.status == AvitoFetchStatus.success
    assert result.source == "scrapingbee"
    assert calls == [False, True]


def test_scrapingbee_failure_keeps_previous_diagnostics(monkeypatch):
    _block_everything(monkeypatch)
    monkeypatch.setattr(settings, "scrapingbee_api_key", "test-key")
    monkeypatch.setattr(settings, "scrapingbee_render_js", False)

    async def _fake_scrapingbee(url: str, *, render_js: bool):
        return None

    monkeypatch.setattr(avito_fetch, "_fetch_scrapingbee", _fake_scrapingbee)

    result = _run(avito_fetch.fetch_avito_html("https://www.avito.ru/items/1234567"))

    # Playwright видел captcha — итоговый статус остаётся captcha, как раньше.
    assert result.status == AvitoFetchStatus.captcha
    assert result.reason == "captcha_challenge"


def test_scrapingbee_not_called_without_key(monkeypatch):
    _block_everything(monkeypatch)
    monkeypatch.setattr(settings, "scrapingbee_api_key", "")
    called = {"value": False}

    async def _fake_scrapingbee(url: str, *, render_js: bool):
        called["value"] = True
        return _valid_listing_html()

    monkeypatch.setattr(avito_fetch, "_fetch_scrapingbee", _fake_scrapingbee)

    result = _run(avito_fetch.fetch_avito_html("https://www.avito.ru/items/1234567"))

    assert called["value"] is False
    assert result.status == AvitoFetchStatus.captcha


def test_scrapingbee_respects_time_budget(monkeypatch):
    _block_everything(monkeypatch)
    monkeypatch.setattr(settings, "scrapingbee_api_key", "test-key")
    monkeypatch.setattr(settings, "avito_fetch_time_budget_sec", 10.0)

    clock = {"value": 1000.0}

    def _fake_monotonic():
        clock["value"] += 6.0
        return clock["value"]

    monkeypatch.setattr(avito_fetch.time, "monotonic", _fake_monotonic)
    called = {"value": False}

    async def _fake_scrapingbee(url: str, *, render_js: bool):
        called["value"] = True
        return _valid_listing_html()

    monkeypatch.setattr(avito_fetch, "_fetch_scrapingbee", _fake_scrapingbee)

    result = _run(avito_fetch.fetch_avito_html("https://www.avito.ru/items/1234567"))

    assert result.status == AvitoFetchStatus.transient_error
    assert result.reason == "time_budget_exceeded"
    assert called["value"] is False
