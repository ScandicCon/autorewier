import asyncio

import app.services.parsers.avito as avito_parser
import app.services.parsers.avito_fetch as avito_fetch
from app.config import settings
from app.services.parsers.avito_fetch import AvitoFetchResult, AvitoFetchStatus


def _run(coro):
    return asyncio.run(coro)


def _valid_listing_html() -> str:
    # Keep payload deterministic and large enough for is_valid_listing_html().
    return (
        '<html><body><div data-marker="item-view/title-info">Listing</div>'
        + ("x" * 8100)
        + "</body></html>"
    )


def test_is_blocked_html_detects_captcha_markers():
    html = "<html><body>Подтвердите, что вы не робот</body></html>"
    assert avito_fetch.is_blocked_html(html)
    assert not avito_fetch.is_blocked_html("<html><body>regular listing page</body></html>")


def test_parse_avito_url_maps_captcha_to_user_facing_error(monkeypatch):
    async def _fake_fetch(_url: str):
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.captcha,
            user_message="Avito показал captcha",
            reason="captcha_challenge",
            action_required="solve_captcha",
        )

    monkeypatch.setattr(avito_parser, "fetch_avito_html", _fake_fetch)

    parsed = _run(avito_parser.parse_avito_url("https://www.avito.ru/items/1234567"))

    assert parsed.parse_ok is False
    assert parsed.parse_status == AvitoFetchStatus.captcha.value
    assert parsed.parse_reason == "captcha_challenge"
    assert parsed.action_required == "solve_captcha"
    assert "captcha" in (parsed.parse_error or "").lower()


def test_fetch_avito_html_fallbacks_to_httpx_after_playwright_block(monkeypatch):
    calls: list[tuple[str, str]] = []
    valid_html = _valid_listing_html()

    async def _fake_playwright(url: str):
        calls.append(("playwright", url))
        return "<html><body>captcha required</body></html>"

    async def _fake_httpx(url: str):
        calls.append(("httpx", url))
        return valid_html, 200, None

    monkeypatch.setattr(settings, "avito_fetch_mode", "auto")
    monkeypatch.setattr(settings, "avito_cache_enabled", False)
    monkeypatch.setattr(settings, "avito_fetch_retry_attempts", 1)
    monkeypatch.setattr(settings, "avito_browser_per_request", False)
    monkeypatch.setattr(avito_fetch, "_fetch_playwright", _fake_playwright)
    monkeypatch.setattr(avito_fetch, "_fetch_httpx", _fake_httpx)
    monkeypatch.setattr(avito_fetch, "_with_retry_pause", lambda attempt: asyncio.sleep(0))

    result = _run(avito_fetch.fetch_avito_html("https://www.avito.ru/items/1234567"))

    assert result.html == valid_html
    assert result.status == AvitoFetchStatus.success
    assert result.source == "httpx"
    assert calls == [
        ("playwright", "https://www.avito.ru/items/1234567"),
        ("httpx", "https://www.avito.ru/items/1234567"),
    ]


def test_fetch_avito_html_retries_with_mobile_url(monkeypatch):
    calls: list[str] = []
    valid_html = _valid_listing_html()

    async def _fake_httpx(url: str):
        calls.append(url)
        if len(calls) == 1:
            return "<html>too short</html>", 200, None
        return valid_html, 200, None

    monkeypatch.setattr(settings, "avito_fetch_mode", "httpx")
    monkeypatch.setattr(settings, "avito_cache_enabled", False)
    monkeypatch.setattr(settings, "avito_fetch_retry_attempts", 1)
    monkeypatch.setattr(avito_fetch, "_fetch_httpx", _fake_httpx)
    monkeypatch.setattr(avito_fetch, "_with_retry_pause", lambda attempt: asyncio.sleep(0))

    result = _run(avito_fetch.fetch_avito_html("https://www.avito.ru/items/1234567"))

    assert result.html == valid_html
    assert result.status == AvitoFetchStatus.success
    assert result.source == "httpx"
    assert calls == [
        "https://www.avito.ru/items/1234567",
        "https://m.avito.ru/items/1234567",
    ]


def test_fetch_avito_html_maps_captcha_error_when_all_attempts_blocked(monkeypatch):
    async def _fake_playwright(_url: str):
        return "<html><body>captcha gate</body></html>"

    async def _fake_httpx(_url: str):
        return None, 429, None

    monkeypatch.setattr(settings, "avito_fetch_mode", "auto")
    monkeypatch.setattr(settings, "avito_cache_enabled", False)
    monkeypatch.setattr(avito_fetch, "_fetch_playwright", _fake_playwright)
    monkeypatch.setattr(avito_fetch, "_fetch_httpx", _fake_httpx)
    monkeypatch.setattr(avito_fetch, "_with_retry_pause", lambda attempt: asyncio.sleep(0))

    result = _run(avito_fetch.fetch_avito_html("https://www.avito.ru/items/1234567"))

    assert result.html is None
    assert result.status == AvitoFetchStatus.captcha
    assert result.reason == "captcha_challenge"
    assert result.action_required == "solve_captcha"
    assert "captcha" in (result.user_message or "").lower()


def test_fetch_avito_html_fails_fast_on_invalid_proxy_config(monkeypatch):
    monkeypatch.setattr(settings, "avito_fetch_mode", "httpx")
    monkeypatch.setattr(settings, "avito_cache_enabled", False)
    monkeypatch.setattr(settings, "avito_proxy", "http://proxy.local:8080")
    monkeypatch.setattr(settings, "avito_proxy_username", "user_only")
    monkeypatch.setattr(settings, "avito_proxy_password", "")

    result = _run(avito_fetch.fetch_avito_html("https://www.avito.ru/items/1234567"))

    assert result.status == AvitoFetchStatus.transient_error
    assert result.reason == "proxy_invalid_config"
    assert result.action_required == "check_proxy_settings"
    proxy_diag = (result.diagnostics or {}).get("proxy", {})
    assert "proxy_auth_incomplete" in proxy_diag.get("issues", [])


def test_fetch_avito_html_respects_time_budget(monkeypatch):
    async def _fake_playwright(_url: str):
        return "<html><body>captcha gate</body></html>"

    async def _fake_httpx(_url: str):
        return None, 429, None

    clock = {"value": 1000.0}

    def _fake_monotonic():
        clock["value"] += 11.0
        return clock["value"]

    monkeypatch.setattr(settings, "avito_fetch_mode", "auto")
    monkeypatch.setattr(settings, "avito_cache_enabled", False)
    monkeypatch.setattr(settings, "avito_fetch_time_budget_sec", 10.0)
    monkeypatch.setattr(settings, "avito_proxy", "")
    monkeypatch.setattr(settings, "avito_proxy_username", "")
    monkeypatch.setattr(settings, "avito_proxy_password", "")
    monkeypatch.setattr(avito_fetch.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(avito_fetch, "_fetch_playwright", _fake_playwright)
    monkeypatch.setattr(avito_fetch, "_fetch_httpx", _fake_httpx)
    monkeypatch.setattr(avito_fetch, "_with_retry_pause", lambda attempt: asyncio.sleep(0))

    result = _run(avito_fetch.fetch_avito_html("https://www.avito.ru/items/1234567"))

    assert result.status == AvitoFetchStatus.transient_error
    assert result.reason == "time_budget_exceeded"
    assert result.action_required == "retry_later_or_proxy"
