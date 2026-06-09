import asyncio

from app.api import routes
from app.schemas import AvitoWarmupRequest, ParseListingRequest, VehicleInput
from app.services.parsers.base import ParsedListing
from app.services.parsers.avito_fetch import (
    AvitoFetchResult,
    AvitoFetchStatus,
    fetch_avito_html,
)
from app.services.parsers.base import parse_listing_url


def test_parse_avito_returns_structured_captcha_status(monkeypatch):
    from app.services.parsers import avito

    async def _fake_fetch(url: str) -> AvitoFetchResult:
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.captcha,
            user_message="Avito показал captcha",
            reason="captcha_challenge",
            action_required="solve_captcha",
        )

    monkeypatch.setattr(avito, "fetch_avito_html", _fake_fetch)
    parsed = asyncio.run(avito.parse_avito_url("https://www.avito.ru/items/1234567"))

    assert parsed.parse_ok is False
    assert parsed.parse_status == AvitoFetchStatus.captcha.value
    assert parsed.parse_reason == "captcha_challenge"
    assert parsed.action_required == "solve_captcha"
    assert "captcha" in (parsed.parse_error or "").lower()


def test_parse_listing_endpoint_model_exposes_parse_status(monkeypatch):
    from starlette.requests import Request
    from types import SimpleNamespace
    from app.config import settings

    async def _fake_parse_listing(url: str) -> ParsedListing:
        return ParsedListing(
            platform="avito",
            vehicle=VehicleInput(),
            raw_title=None,
            parse_ok=False,
            parse_error="captcha",
            parse_status=AvitoFetchStatus.captcha.value,
            parse_reason="captcha_challenge",
            action_required="solve_captcha",
            listing_repairs=[],
        )

    monkeypatch.setattr(routes, "parse_listing_url", _fake_parse_listing)
    monkeypatch.setattr(settings, "rate_limit_enabled", False)
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/parse-listing",
            "headers": [],
            "client": ("127.0.0.1", 5050),
            "scheme": "http",
            "server": ("testserver", 80),
        }
    )
    response = asyncio.run(
        routes.parse_listing(
            ParseListingRequest(url="https://www.avito.ru/items/1234567"),
            request=request,
            user=SimpleNamespace(id=1),
        )
    )

    assert response.parse_status == AvitoFetchStatus.captcha.value
    assert response.parse_reason == "captcha_challenge"
    assert response.action_required == "solve_captcha"


def test_fetch_avito_html_retries_are_bounded(monkeypatch):
    from app.services.parsers import avito_fetch
    from app.config import settings

    calls = {"pw": 0, "pw_profile": 0, "http": 0}

    async def _fake_playwright(url: str, *, use_persistent: bool | None = None):
        if use_persistent:
            calls["pw_profile"] += 1
        else:
            calls["pw"] += 1
        return "<html><body>captcha challenge</body></html>"

    async def _fake_httpx(url: str):
        calls["http"] += 1
        return None, 429, None

    monkeypatch.setattr(settings, "avito_fetch_mode", "auto")
    monkeypatch.setattr(settings, "avito_fetch_retry_attempts", 2)
    monkeypatch.setattr(settings, "avito_captcha_retry_attempts", 1)
    monkeypatch.setattr(settings, "avito_browser_per_request", True)
    monkeypatch.setattr(settings, "avito_cache_enabled", False)
    monkeypatch.setattr(avito_fetch, "_fetch_playwright", _fake_playwright)
    monkeypatch.setattr(avito_fetch, "_fetch_httpx", _fake_httpx)
    monkeypatch.setattr(avito_fetch, "_with_retry_pause", lambda attempt: asyncio.sleep(0))

    result = asyncio.run(fetch_avito_html("https://www.avito.ru/moskva/avtomobili/test"))

    assert result.status == AvitoFetchStatus.captcha
    assert calls["pw"] == 2
    assert calls["pw_profile"] == 4
    assert calls["http"] == 2


def test_avito_warmup_endpoint_returns_structured_contract(monkeypatch):
    async def _fake_warmup(_url: str | None):
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.transient_error,
            reason="proxy_auth_failed",
            action_required="check_proxy_credentials",
            user_message="proxy auth failed",
            attempts=1,
            diagnostics={"proxy": {"configured": True, "has_auth": True}},
        )

    monkeypatch.setattr(routes, "warmup_avito_session", _fake_warmup)

    response = asyncio.run(
        routes.avito_warmup(
            AvitoWarmupRequest(url="https://www.avito.ru/items/1234567"),
            user=object(),
        )
    )

    assert response.status == AvitoFetchStatus.transient_error.value
    assert response.reason == "proxy_auth_failed"
    assert response.action_required == "check_proxy_credentials"
    assert response.attempts == 1
    assert (response.diagnostics or {}).get("proxy", {}).get("configured") is True


def test_repair_text_fixes_common_mojibake():
    from app.services.parsers import avito as avito_parser

    broken = "ÐÐÐ (LADA) 21099, Ð³Ð¾Ð»ÑÐ±Ð¾Ð¹"
    fixed = avito_parser._repair_text(broken)  # noqa: SLF001 - parser helper check
    assert fixed is not None
    assert "Ð" not in fixed
    assert "ВАЗ" in fixed


def test_parse_listing_drom_returns_structured_success(monkeypatch):
    from app.services.parsers import base as base_parser

    async def _fake_fetch(_url: str, extra_headers: dict | None = None):
        return (
            """
            <html><body>
            <h1>Toyota Camry, 2015</h1>
            <div class='auto-price'>1 350 000 ₽</div>
            <li>Год выпуска: 2015</li>
            <li>Пробег: 165000 км</li>
            <div data-ftid="bull_description">Без ДТП, обслуживалась вовремя</div>
            </body></html>
            """,
            200,
            None,
        )

    monkeypatch.setattr(base_parser, "_fetch_html", _fake_fetch)
    parsed = asyncio.run(parse_listing_url("https://auto.drom.ru/item/123456.html"))
    assert parsed.platform == "drom"
    assert parsed.parse_ok is True
    assert parsed.parse_status == "success"
    assert parsed.vehicle.year == 2015
    assert parsed.vehicle.price_rub == 1350000


def test_parse_listing_youla_returns_structured_blocked(monkeypatch):
    from app.services.parsers import base as base_parser

    async def _fake_fetch(_url: str, extra_headers: dict | None = None):
        return ("<html><body>captcha required</body></html>", 200, None)

    monkeypatch.setattr(base_parser, "_fetch_html", _fake_fetch)
    parsed = asyncio.run(parse_listing_url("https://youla.ru/some/listing"))
    assert parsed.platform == "youla"
    assert parsed.parse_ok is False
    assert parsed.parse_status == "blocked"
    assert parsed.parse_reason == "blocked_markup_detected"
