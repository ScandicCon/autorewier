"""Сравнение цены авто с рыночными ценами через парсинг Avito."""
from __future__ import annotations

import logging
import re
import statistics
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.schemas import MarketComparison, VehicleInput

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

MIN_SAMPLE = 3  # минимум объявлений для расчёта медианы
ABOVE_THRESHOLD = 5.0   # % выше рынка — уже «дороже»
BELOW_THRESHOLD = -5.0  # % ниже рынка — «выгодная цена»


def _build_search_url(vehicle: VehicleInput) -> str:
    brand = (vehicle.brand or "").strip()
    model = (vehicle.model or "").strip()
    query = f"{brand} {model}".strip()
    q = quote_plus(query)
    url = f"https://www.avito.ru/rossiya/avtomobili?q={q}"
    if vehicle.year:
        # Ищем +/- 2 года от года авто
        url += f"&pmin={max(0, vehicle.year - 2)}&pmax={vehicle.year + 2}"
        # На самом деле это поля для цены, Avito использует другие параметры для года
        # Правильные параметры года: params[109] = значение года
        url = f"https://www.avito.ru/rossiya/avtomobili?q={q}"
    return url


def _parse_price(text: str) -> int | None:
    """Извлекает целочисленную цену из текста (рубли)."""
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    val = int(digits)
    # Фильтруем явно нереалистичные значения
    if val < 30_000 or val > 50_000_000:
        return None
    return val


def _extract_prices_from_html(html: str) -> list[int]:
    """Парсит цены объявлений со страницы выдачи Avito."""
    soup = BeautifulSoup(html, "lxml")
    prices: list[int] = []

    # Набор селекторов для цен на странице выдачи Avito
    selectors = [
        # Новый Avito: data-marker
        '[data-marker="item-price"] strong',
        '[data-marker="item-price"] span',
        '[data-marker="price-value"]',
        # Структурированные данные
        'meta[itemprop="price"]',
        '[itemprop="price"]',
        # Классы цен (изменяются, но паттерн сохраняется)
        '.iva-item-price-_tfBR',
        '.price-text-_YGDY',
        '[class*="price-text"]',
        '[class*="item-price"]',
        # JSON-LD fallback ниже
    ]

    for sel in selectors:
        elements = soup.select(sel)
        for el in elements:
            if el.name == "meta":
                raw = el.get("content", "")
            else:
                raw = el.get_text(separator=" ", strip=True)
            price = _parse_price(raw)
            if price:
                prices.append(price)
        if len(prices) >= 20:
            break

    # Если ничего — попробуем JSON-LD
    if len(prices) < MIN_SAMPLE:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                import json
                data = json.loads(script.string or "")
                items = data if isinstance(data, list) else data.get("itemListElement", [])
                for item in items:
                    offers = item.get("item", {}).get("offers", {}) if isinstance(item, dict) else {}
                    p = offers.get("price") if offers else None
                    if p:
                        price = _parse_price(str(p))
                        if price:
                            prices.append(price)
            except Exception:
                continue

    # Дедупликация: убираем дубли
    return list(dict.fromkeys(prices))


async def _fetch_search_page(url: str) -> str | None:
    """Загружает HTML страницы поиска через httpx."""
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=15.0,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
                "Referer": "https://www.avito.ru/",
            },
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
            if resp.status_code in (403, 429):
                logger.warning("market_comparison: Avito blocked (%s)", resp.status_code)
            return None
    except httpx.HTTPError as exc:
        logger.warning("market_comparison fetch error: %s", exc)
        return None


def _is_captcha_or_blocked(html: str) -> bool:
    sample = html[:10000].lower()
    markers = ("captcha", "hcaptcha", "подтвердите", "доступ ограничен", "cf-challenge")
    return any(m in sample for m in markers)


async def get_market_comparison(vehicle: VehicleInput) -> MarketComparison | None:
    """
    Строит сравнение цены авто с рыночными ценами по Avito.
    Возвращает None при ошибке / капче / недостатке данных.
    """
    if not vehicle.brand or not vehicle.model or not vehicle.price_rub:
        return None

    search_url = _build_search_url(vehicle)

    try:
        html = await _fetch_search_page(search_url)
        if not html:
            return None

        if _is_captcha_or_blocked(html):
            logger.warning("market_comparison: captcha/blocked by Avito")
            return None

        prices = _extract_prices_from_html(html)

        if len(prices) < MIN_SAMPLE:
            logger.info(
                "market_comparison: not enough prices (%d found, need %d)",
                len(prices),
                MIN_SAMPLE,
            )
            return None

        # Ограничиваем до 30 цен и убираем выбросы (±3 IQR)
        prices_sorted = sorted(prices)[:30]
        if len(prices_sorted) >= 6:
            q1 = prices_sorted[len(prices_sorted) // 4]
            q3 = prices_sorted[3 * len(prices_sorted) // 4]
            iqr = q3 - q1
            prices_sorted = [
                p for p in prices_sorted
                if (q1 - 3 * iqr) <= p <= (q3 + 3 * iqr)
            ] or prices_sorted

        if len(prices_sorted) < MIN_SAMPLE:
            return None

        median_price = int(statistics.median(prices_sorted))
        sample_count = len(prices_sorted)
        delta_pct = round((vehicle.price_rub - median_price) / median_price * 100, 1)

        if delta_pct > ABOVE_THRESHOLD:
            verdict = "above_market"
            diff_rub = vehicle.price_rub - median_price
            comment = (
                f"Цена на {delta_pct:.1f}% выше медианы рынка ({median_price:,} ₽). "
                f"Есть пространство для торга ~{diff_rub:,} ₽.".replace(",", " ")
            )
        elif delta_pct < BELOW_THRESHOLD:
            verdict = "below_market"
            diff_rub = median_price - vehicle.price_rub
            comment = (
                f"Цена на {abs(delta_pct):.1f}% ниже медианы рынка ({median_price:,} ₽). "
                f"Выгодная цена — проверьте состояние тщательнее.".replace(",", " ")
            )
        else:
            verdict = "fair_price"
            comment = (
                f"Цена соответствует рынку (медиана {median_price:,} ₽, "
                f"выборка {sample_count} объявлений).".replace(",", " ")
            )

        return MarketComparison(
            median_price=median_price,
            sample_count=sample_count,
            delta_pct=delta_pct,
            verdict=verdict,
            comment=comment,
            search_url=search_url,
        )

    except Exception as exc:
        logger.warning("market_comparison unexpected error: %s", exc)
        return None
