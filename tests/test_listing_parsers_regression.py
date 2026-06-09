import asyncio

from app.services.parsers import base as parsers_base


def test_parse_listing_url_supports_drom_platform(monkeypatch):
    async def _fake_fetch_html(_url: str, extra_headers: dict | None = None) -> str | None:
        return """
        <html>
          <body>
            <h1>Toyota Camry, 2014</h1>
            <div class="auto-price">1 250 000 ₽</div>
          </body>
        </html>
        """

    monkeypatch.setattr(parsers_base, "_fetch_html", _fake_fetch_html)

    parsed = asyncio.run(parsers_base.parse_listing_url("https://auto.drom.ru/toyota/camry-42"))
    assert parsed.platform == "drom"
    assert parsed.raw_title == "Toyota Camry, 2014"
    assert parsed.vehicle.brand == "Toyota"
    assert parsed.vehicle.model == "Camry"
    assert parsed.vehicle.price_rub == 1250000


def test_parse_listing_url_supports_additional_generic_platform(monkeypatch):
    async def _fake_fetch_html(_url: str, extra_headers: dict | None = None) -> str | None:
        return """
        <html>
          <body>
            <h1>Skoda Octavia</h1>
          </body>
        </html>
        """

    monkeypatch.setattr(parsers_base, "_fetch_html", _fake_fetch_html)

    parsed = asyncio.run(parsers_base.parse_listing_url("https://youla.ru/item/skoda-octavia-123"))
    assert parsed.platform == "youla"
    assert parsed.raw_title == "Skoda Octavia"
    assert parsed.vehicle.brand == "Skoda"
    assert parsed.vehicle.model == "Octavia"
