import json
import re
import statistics
from pathlib import Path
from urllib.parse import quote_plus

import httpx
from bs4 import BeautifulSoup

from app.schemas import AvitoPartOffer, PartPriceBlock, VehicleInput

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
DATA_DIR = Path(__file__).resolve().parent.parent / "data"
MAX_OFFERS = 5


def build_avito_search_url(query: str) -> str:
    q = quote_plus(query)
    return f"https://www.avito.ru/rossiya/zapchasti_i_aksessuary?q={q}"


def _parse_price(text: str) -> int | None:
    digits = re.sub(r"\D", "", text)
    if not digits:
        return None
    val = int(digits)
    return val if val > 100 else None


def _vehicle_suffix(vehicle: VehicleInput) -> str:
    parts = [vehicle.brand, vehicle.model, str(vehicle.year) if vehicle.year else None]
    return " ".join(p for p in parts if p)


async def _fetch_html(url: str) -> str | None:
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=18.0,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
    except httpx.HTTPError:
        return None
    return None


async def search_avito_parts(query: str) -> list[AvitoPartOffer]:
    url = build_avito_search_url(query)
    html = await _fetch_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    offers: list[AvitoPartOffer] = []

    for item in soup.select('[data-marker="item"], .iva-item-root, [itemtype*="Product"]'):
        title_el = item.select_one('[itemprop="name"], h3, [data-marker="item-title"]')
        price_el = item.select_one('[itemprop="price"], [data-marker="item-price"], meta[itemprop="price"]')
        link_el = item.select_one("a[href*='/zapchasti']") or item.select_one("a[href]")

        title = title_el.get_text(strip=True) if title_el else None
        if not title:
            continue

        if price_el and price_el.name == "meta":
            price = _parse_price(price_el.get("content", ""))
        else:
            price = _parse_price(price_el.get_text() if price_el else "")

        if not price:
            continue

        href = link_el.get("href", "") if link_el else ""
        if href.startswith("/"):
            href = f"https://www.avito.ru{href}"
        if not href.startswith("http"):
            continue

        offers.append(AvitoPartOffer(title=title[:120], price_rub=price, url=href))
        if len(offers) >= MAX_OFFERS:
            break

    return offers


async def _search_exist_prices(query: str) -> list[int]:
    """Цены с Exist.ru — только для расчёта, без ссылок пользователю."""
    q = quote_plus(query)
    url = f"https://exist.ru/Price/?pcode={q}"
    html = await _fetch_html(url)
    if not html:
        url = f"https://exist.ru/Search/?text={q}"
        html = await _fetch_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    prices: list[int] = []
    for el in soup.select(".price, .cost, [class*='price']"):
        p = _parse_price(el.get_text())
        if p and 500 < p < 5_000_000:
            prices.append(p)
        if len(prices) >= 10:
            break
    return prices


async def _search_emex_prices(query: str) -> list[int]:
    """Цены с Emex — только для расчёта."""
    q = quote_plus(query)
    url = f"https://emex.ru/search?text={q}"
    html = await _fetch_html(url)
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    prices: list[int] = []
    for el in soup.select("[class*='price'], .part-price"):
        p = _parse_price(el.get_text())
        if p and 500 < p < 5_000_000:
            prices.append(p)
        if len(prices) >= 10:
            break
    return prices


def _stats(prices: list[int]) -> tuple[int | None, int | None, int | None]:
    if not prices:
        return None, None, None
    return min(prices), max(prices), int(statistics.median(prices))


def _load_part_queries() -> dict[str, list[str]]:
    with open(DATA_DIR / "part_queries.json", encoding="utf-8") as f:
        return json.load(f)


def _categories_from_defects(defects: str | None, repair_categories: list[str]) -> list[str]:
    cats = list(dict.fromkeys(repair_categories))
    if not cats:
        cats = ["Прочее"]
    return cats[:4]


async def build_parts_pricing(
    vehicle: VehicleInput,
    defects: str | None,
    repair_categories: list[str],
) -> list[PartPriceBlock]:
    queries_map = _load_part_queries()
    suffix = _vehicle_suffix(vehicle)
    blocks: list[PartPriceBlock] = []

    for category in _categories_from_defects(defects, repair_categories):
        part_names = queries_map.get(category, queries_map.get("Прочее", ["запчасть"]))[:2]
        for part_name in part_names:
            query = f"{part_name} {suffix}".strip()
            avito_offers = await search_avito_parts(query)
            avito_prices = [o.price_rub for o in avito_offers]

            exist_prices = await _search_exist_prices(query)
            emex_prices = await _search_emex_prices(query)
            market_prices = exist_prices + emex_prices
            market_sources: list[str] = []
            if exist_prices:
                market_sources.append("Exist.ru")
            if emex_prices:
                market_sources.append("Emex.ru")

            a_min, a_max, a_med = _stats(avito_prices)
            m_min, m_max, m_med = _stats(market_prices)

            all_prices = avito_prices + market_prices
            est_min, est_max, est_med = _stats(all_prices)

            note_parts = []
            if market_sources and m_min is not None:
                note_parts.append(
                    f"Магазины ({', '.join(market_sources)}): ориентир {m_min:,}–{m_max:,} ₽ "
                    f"(ссылки не предоставляются по правилам сервиса)".replace(",", " ")
                )
            if not avito_offers and not market_prices:
                note_parts.append("Не удалось получить актуальные цены — проверьте вручную на Авито")

            blocks.append(
                PartPriceBlock(
                    category=category,
                    part_name=part_name,
                    search_query=query,
                    search_url=build_avito_search_url(query),
                    avito_offers=avito_offers,
                    avito_min=a_min,
                    avito_max=a_max,
                    avito_median=a_med,
                    market_min=m_min,
                    market_max=m_max,
                    market_median=m_med,
                    market_sources=market_sources,
                    estimate_min=est_min,
                    estimate_max=est_max,
                    estimate_median=est_med,
                    note=" ".join(note_parts),
                    links_available=bool(avito_offers),
                )
            )

    return blocks
