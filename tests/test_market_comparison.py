"""Тесты для app.services.market_comparison.get_market_comparison."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.schemas import MarketComparison, VehicleInput
from app.services.market_comparison import (
    ABOVE_THRESHOLD,
    BELOW_THRESHOLD,
    MIN_SAMPLE,
    _extract_prices_from_html,
    _parse_price,
    get_market_comparison,
)


# ---------------------------------------------------------------------------
# Вспомогательные фабрики
# ---------------------------------------------------------------------------

def _make_vehicle(price_rub: int, brand: str = "Toyota", model: str = "Camry",
                  year: int = 2015) -> VehicleInput:
    return VehicleInput(brand=brand, model=model, year=year, price_rub=price_rub)


def _prices_to_fake_html(prices: list[int]) -> str:
    """Генерирует минимальный HTML с ценами в data-marker атрибутах."""
    items = "\n".join(
        f'<div data-marker="item-price"><strong>{p:,} ₽</strong></div>'
        for p in prices
    )
    return f"<html><body>{items}</body></html>"


# ---------------------------------------------------------------------------
# Тесты через мок _fetch_search_page
# ---------------------------------------------------------------------------

def test_market_comparison_above(monkeypatch: pytest.MonkeyPatch):
    """
    Парсер возвращает [1_000_000, 1_100_000, 900_000], цена = 1_300_000
    → delta_pct > 0, verdict = 'above_market'.
    """
    sample_prices = [1_000_000, 1_100_000, 900_000]
    fake_html = _prices_to_fake_html(sample_prices)

    async def _fake_fetch(url: str) -> str:
        return fake_html

    with patch("app.services.market_comparison._fetch_search_page", side_effect=_fake_fetch):
        vehicle = _make_vehicle(price_rub=1_300_000)
        result = asyncio.run(get_market_comparison(vehicle))

    assert result is not None
    assert isinstance(result, MarketComparison)
    assert result.delta_pct > 0
    assert result.verdict == "above_market"
    assert result.sample_count >= MIN_SAMPLE


def test_market_comparison_below(monkeypatch: pytest.MonkeyPatch):
    """
    Парсер возвращает [1_000_000, 1_100_000, 900_000], цена = 700_000
    → delta_pct < 0, verdict = 'below_market'.
    """
    sample_prices = [1_000_000, 1_100_000, 900_000]
    fake_html = _prices_to_fake_html(sample_prices)

    async def _fake_fetch(url: str) -> str:
        return fake_html

    with patch("app.services.market_comparison._fetch_search_page", side_effect=_fake_fetch):
        vehicle = _make_vehicle(price_rub=700_000)
        result = asyncio.run(get_market_comparison(vehicle))

    assert result is not None
    assert isinstance(result, MarketComparison)
    assert result.delta_pct < 0
    assert result.verdict == "below_market"


def test_market_comparison_fair_price(monkeypatch: pytest.MonkeyPatch):
    """
    Цена совпадает с медианой рынка (±ABOVE_THRESHOLD%) → verdict = 'fair_price'.
    """
    sample_prices = [1_000_000, 1_050_000, 950_000, 980_000, 1_020_000]
    fake_html = _prices_to_fake_html(sample_prices)

    async def _fake_fetch(url: str) -> str:
        return fake_html

    with patch("app.services.market_comparison._fetch_search_page", side_effect=_fake_fetch):
        # Медиана ≈ 1 000 000; цена 1 010 000 = +1% — в диапазоне fair
        vehicle = _make_vehicle(price_rub=1_010_000)
        result = asyncio.run(get_market_comparison(vehicle))

    assert result is not None
    assert result.verdict == "fair_price"
    assert BELOW_THRESHOLD <= result.delta_pct <= ABOVE_THRESHOLD


def test_market_comparison_no_results(monkeypatch: pytest.MonkeyPatch):
    """
    Парсер возвращает [] (нет цен в HTML) → get_market_comparison возвращает None.
    """
    async def _fake_fetch(url: str) -> str:
        return "<html><body>Нет объявлений</body></html>"

    with patch("app.services.market_comparison._fetch_search_page", side_effect=_fake_fetch):
        vehicle = _make_vehicle(price_rub=1_000_000)
        result = asyncio.run(get_market_comparison(vehicle))

    assert result is None


def test_market_comparison_graceful_degradation(monkeypatch: pytest.MonkeyPatch):
    """
    Если _fetch_search_page кидает Exception → возвращает None, не ломает приложение.
    """
    async def _raising_fetch(url: str) -> str:
        raise RuntimeError("connection refused")

    with patch("app.services.market_comparison._fetch_search_page", side_effect=_raising_fetch):
        vehicle = _make_vehicle(price_rub=1_000_000)
        result = asyncio.run(get_market_comparison(vehicle))

    assert result is None


def test_market_comparison_returns_none_without_price():
    """Если у vehicle нет price_rub → сразу возвращает None без HTTP запроса."""
    vehicle = VehicleInput(brand="Toyota", model="Camry", year=2015)
    result = asyncio.run(get_market_comparison(vehicle))
    assert result is None


def test_market_comparison_returns_none_without_brand():
    """Если у vehicle нет brand → сразу возвращает None без HTTP запроса."""
    vehicle = VehicleInput(model="Camry", year=2015, price_rub=1_000_000)
    result = asyncio.run(get_market_comparison(vehicle))
    assert result is None


def test_market_comparison_below_min_sample_returns_none(monkeypatch: pytest.MonkeyPatch):
    """
    Парсер возвращает меньше MIN_SAMPLE цен → возвращает None
    (недостаточно данных для статистики).
    """
    # MIN_SAMPLE = 3, возвращаем только 2 цены
    sample_prices = [1_000_000, 1_100_000]
    fake_html = _prices_to_fake_html(sample_prices)

    async def _fake_fetch(url: str) -> str:
        return fake_html

    with patch("app.services.market_comparison._fetch_search_page", side_effect=_fake_fetch):
        vehicle = _make_vehicle(price_rub=1_000_000)
        result = asyncio.run(get_market_comparison(vehicle))

    assert result is None


# ---------------------------------------------------------------------------
# Юнит-тесты внутренних вспомогательных функций
# ---------------------------------------------------------------------------

def test_parse_price_valid():
    assert _parse_price("1 200 000 ₽") == 1_200_000
    assert _parse_price("950000") == 950_000


def test_parse_price_invalid():
    assert _parse_price("бесплатно") is None
    assert _parse_price("10") is None  # слишком маленькое значение
    assert _parse_price("100000000000") is None  # слишком большое значение
