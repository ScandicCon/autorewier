import json
import re
from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

from app.schemas import ParseListingStatusEnum, VehicleInput

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
TIMEOUT = 15.0


@dataclass
class ParsedListing:
    platform: str | None
    vehicle: VehicleInput
    raw_title: str | None = None
    parse_ok: bool = False
    parse_error: str | None = None
    listing_repairs: list[str] | None = None
    parse_status: str | None = None
    parse_reason: str | None = None
    action_required: str | None = None
    photo_urls: list[str] | None = None

    def __post_init__(self):
        if self.listing_repairs is None:
            self.listing_repairs = []
        if self.photo_urls is None:
            self.photo_urls = []


def _detect_platform(url: str) -> str | None:
    host = urlparse(url).netloc.lower()
    if "avito.ru" in host:
        return "avito"
    if "auto.ru" in host:
        return "auto.ru"
    if "drom.ru" in host:
        return "drom"
    if "youla.ru" in host:
        return "youla"
    return None


def _parse_int(text: str | None) -> int | None:
    if not text:
        return None
    digits = re.sub(r"\D", "", text)
    return int(digits) if digits else None


def _split_brand_model(title: str) -> tuple[str | None, str | None]:
    parts = title.strip().split(",", 1)[0].split()
    if len(parts) >= 2:
        return parts[0], " ".join(parts[1:])
    if parts:
        return parts[0], None
    return None, None


def _to_structured_error(
    platform: str | None,
    *,
    status: ParseListingStatusEnum,
    reason: str,
    error: str,
    action_required: str | None = None,
) -> ParsedListing:
    return ParsedListing(
        platform=platform or "unknown",
        vehicle=VehicleInput(),
        parse_ok=False,
        parse_error=error,
        parse_status=status.value,
        parse_reason=reason,
        action_required=action_required,
    )


def _looks_blocked(html: str) -> bool:
    sample = html[:15000].lower()
    return any(
        marker in sample
        for marker in (
            "captcha",
            "подтвердите, что вы не робот",
            "access denied",
            "firewall",
            "доступ ограничен",
        )
    )


def _parse_specs_map(soup: BeautifulSoup) -> dict[str, str]:
    specs: dict[str, str] = {}
    for row in soup.select("li, .css-1x4jcd6, .CardInfoRow, .CardInfoSummarySimpleRow"):
        text = row.get_text(" ", strip=True)
        if ":" not in text:
            continue
        left, right = text.split(":", 1)
        key = left.strip().lower()
        value = right.strip()
        if key and value:
            specs[key] = value
    for dl in soup.select("dl"):
        dts = dl.select("dt")
        dds = dl.select("dd")
        for dt, dd in zip(dts, dds):
            key = dt.get_text(" ", strip=True).lower()
            val = dd.get_text(" ", strip=True)
            if key and val:
                specs[key] = val
    return specs


async def _fetch_html(
    url: str, extra_headers: dict | None = None
) -> tuple[str | None, int | None, str | None]:
    headers = {"User-Agent": USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=TIMEOUT,
            headers=headers,
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text, resp.status_code, None
            return None, resp.status_code, None
    except httpx.HTTPError as exc:
        return None, None, str(exc)


def _parse_avito(soup: BeautifulSoup, url: str) -> ParsedListing:
    title_el = soup.select_one('h1[data-marker="item-view/title-info"]') or soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else None
    brand, model = _split_brand_model(title or "")

    price_el = soup.select_one('[data-marker="item-view/item-price"]') or soup.select_one(
        'span[itemprop="price"]'
    )
    price = _parse_int(price_el.get_text() if price_el else None)

    params = {}
    for row in soup.select('[data-marker="item-view/item-params"] li, .params-paramsList li'):
        text = row.get_text(" ", strip=True)
        if ":" in text:
            k, v = text.split(":", 1)
            params[k.strip().lower()] = v.strip()

    year = _parse_int(params.get("год выпуска") or params.get("год"))
    mileage = _parse_int(params.get("пробег"))
    engine = params.get("двигатель") or params.get("объём двигателя")
    transmission = params.get("коробка передач") or params.get("кпп")
    drive = params.get("привод")
    body = params.get("тип кузова") or params.get("кузов")
    color = params.get("цвет")

    desc_el = soup.select_one('[data-marker="item-view/item-description"]')
    description = desc_el.get_text("\n", strip=True) if desc_el else None

    parse_ok = bool((brand or model or title) and (price or year or mileage or description))
    return ParsedListing(
        platform="avito",
        raw_title=title,
        vehicle=VehicleInput(
            brand=brand,
            model=model,
            year=year,
            mileage_km=mileage,
            price_rub=price,
            engine=engine,
            transmission=transmission,
            drive=drive,
            body_type=body,
            color=color,
            description=description,
        ),
        parse_ok=parse_ok,
        parse_status=(
            ParseListingStatusEnum.success.value
            if parse_ok
            else ParseListingStatusEnum.invalid_html.value
        ),
        parse_reason=None if parse_ok else "avito_fields_not_extracted",
        action_required=None if parse_ok else "fill_manual",
        parse_error=(
            None if parse_ok else "Не удалось извлечь ключевые поля из объявления Avito."
        ),
    )


def _parse_auto_ru(soup: BeautifulSoup, url: str) -> ParsedListing:
    title_el = soup.select_one("h1.CardHead__title") or soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else None
    brand, model = _split_brand_model(title or "")

    price_el = soup.select_one(".OfferPriceCaption__price") or soup.select_one(
        'meta[itemprop="price"]'
    )
    if price_el and price_el.name == "meta":
        price = _parse_int(price_el.get("content"))
    else:
        price = _parse_int(price_el.get_text() if price_el else None)

    specs = {}
    for row in soup.select(".CardInfoSummarySimpleRow, .CardInfoRow"):
        label = row.select_one(".CardInfoSummarySimpleRow__label, .CardInfoRow__cell")
        value = row.select_one(".CardInfoSummarySimpleRow__value, .CardInfoRow__cell:last-child")
        if label and value:
            specs[label.get_text(strip=True).lower()] = value.get_text(strip=True)

    year = _parse_int(specs.get("год выпуска") or specs.get("год"))
    mileage = _parse_int(specs.get("пробег"))
    engine = specs.get("двигатель")
    transmission = specs.get("коробка") or specs.get("кпп")
    drive = specs.get("привод")

    desc_el = soup.select_one(".CardDescriptionHTML")
    description = desc_el.get_text("\n", strip=True) if desc_el else None

    parse_ok = bool((brand or model or title) and (price or year or mileage or description))
    return ParsedListing(
        platform="auto.ru",
        raw_title=title,
        vehicle=VehicleInput(
            brand=brand,
            model=model,
            year=year,
            mileage_km=mileage,
            price_rub=price,
            engine=engine,
            transmission=transmission,
            drive=drive,
            description=description,
        ),
        parse_ok=parse_ok,
        parse_status=(
            ParseListingStatusEnum.success.value
            if parse_ok
            else ParseListingStatusEnum.invalid_html.value
        ),
        parse_reason=None if parse_ok else "auto_ru_fields_not_extracted",
        action_required=None if parse_ok else "fill_manual",
        parse_error=(
            None if parse_ok else "Не удалось извлечь ключевые поля из объявления Auto.ru."
        ),
    )


def _parse_drom(soup: BeautifulSoup, url: str) -> ParsedListing:
    title_el = soup.select_one("h1") or soup.select_one(".bull-item-title")
    title = title_el.get_text(strip=True) if title_el else None
    brand, model = _split_brand_model(title or "")

    price_el = (
        soup.select_one(".auto-price")
        or soup.select_one('[data-field="price"]')
        or soup.select_one('[data-ftid="bull_price"]')
        or soup.select_one('[itemprop="price"]')
    )
    price = _parse_int(price_el.get_text() if price_el else None)
    if not price and price_el and price_el.name == "meta":
        price = _parse_int(price_el.get("content"))

    specs = _parse_specs_map(soup)
    year = _parse_int(specs.get("год выпуска") or specs.get("год") or specs.get("year"))
    mileage = _parse_int(specs.get("пробег") or specs.get("пробег, км") or specs.get("mileage"))
    engine = specs.get("двигатель") or specs.get("engine")
    transmission = specs.get("коробка передач") or specs.get("кпп")
    drive = specs.get("привод")
    body = specs.get("кузов") or specs.get("тип кузова")
    color = specs.get("цвет")
    desc_el = (
        soup.select_one(".b-media-cont_margin_t_20")
        or soup.select_one('[data-ftid="bull_description"]')
        or soup.select_one('[itemprop="description"]')
    )
    description = desc_el.get_text("\n", strip=True) if desc_el else None
    parse_ok = bool((brand or model or title) and (price or year or mileage or description))

    return ParsedListing(
        platform="drom",
        raw_title=title,
        vehicle=VehicleInput(
            brand=brand,
            model=model,
            year=year,
            mileage_km=mileage,
            price_rub=price,
            engine=engine,
            transmission=transmission,
            drive=drive,
            body_type=body,
            color=color,
            description=description,
        ),
        parse_ok=parse_ok,
        parse_status=(
            ParseListingStatusEnum.success.value
            if parse_ok
            else ParseListingStatusEnum.invalid_html.value
        ),
        parse_reason=None if parse_ok else "drom_fields_not_extracted",
        action_required=None if parse_ok else "fill_manual",
        parse_error=(
            None if parse_ok else "Не удалось извлечь ключевые поля из объявления Drom."
        ),
    )


def _parse_youla(soup: BeautifulSoup, url: str) -> ParsedListing:
    title_el = soup.select_one("h1") or soup.select_one("[data-test-id='ad-title']")
    title = title_el.get_text(strip=True) if title_el else None
    brand, model = _split_brand_model(title or "")
    price = None
    for price_el in soup.select(
        "[data-test-id='ad-price'], .Price, meta[itemprop='price'], [itemprop='price']"
    ):
        if price_el.name == "meta":
            price = _parse_int(price_el.get("content"))
        else:
            price = _parse_int(price_el.get_text())
        if price:
            break
    desc_el = soup.select_one("[data-test-id='ad-description']") or soup.select_one(
        ".AdvertDescription"
    )
    description = desc_el.get_text("\n", strip=True) if desc_el else None
    specs = _parse_specs_map(soup)
    year = _parse_int(specs.get("год") or specs.get("год выпуска"))
    mileage = _parse_int(specs.get("пробег") or specs.get("пробег, км"))
    transmission = specs.get("кпп") or specs.get("коробка передач")
    drive = specs.get("привод")
    body = specs.get("кузов") or specs.get("тип кузова")
    color = specs.get("цвет")
    if not (price and year):
        for script in soup.select('script[type="application/ld+json"]'):
            if not script.string:
                continue
            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue
            items = data if isinstance(data, list) else [data]
            for item in items:
                if not isinstance(item, dict):
                    continue
                year = year or _parse_int(str(item.get("vehicleModelDate") or ""))
                price = price or _parse_int(str(item.get("price") or ""))
                description = description or (
                    item.get("description")
                    if isinstance(item.get("description"), str)
                    else None
                )
                if not title and isinstance(item.get("name"), str):
                    title = item["name"]
                    brand, model = _split_brand_model(title)
    parse_ok = bool((brand or model or title) and (price or year or mileage or description))
    return ParsedListing(
        platform="youla",
        raw_title=title,
        vehicle=VehicleInput(
            brand=brand,
            model=model,
            year=year,
            mileage_km=mileage,
            price_rub=price,
            transmission=transmission,
            drive=drive,
            body_type=body,
            color=color,
            description=description,
        ),
        parse_ok=parse_ok,
        parse_status=(
            ParseListingStatusEnum.success.value
            if parse_ok
            else ParseListingStatusEnum.invalid_html.value
        ),
        parse_reason=None if parse_ok else "youla_fields_not_extracted",
        action_required=None if parse_ok else "fill_manual",
        parse_error=(
            None if parse_ok else "Не удалось извлечь ключевые поля из объявления Youla."
        ),
    )


async def parse_listing_url(url: str) -> ParsedListing:
    from app.services.parsers.avito import is_avito_url, parse_avito_url
    from app.services.parsers.drom import is_drom_url, parse_drom_url

    if is_avito_url(url):
        return await parse_avito_url(url)

    if is_drom_url(url):
        return await parse_drom_url(url)

    platform = _detect_platform(url)
    if not platform:
        return _to_structured_error(
            None,
            status=ParseListingStatusEnum.failed,
            reason="unsupported_platform",
            error="Ссылка не относится к поддерживаемым площадкам (Avito, Auto.ru, Drom, Youla).",
            action_required="provide_supported_url",
        )
    fetch_result = await _fetch_html(url)
    if isinstance(fetch_result, tuple):
        html, http_status, fetch_error = fetch_result
    else:
        # Legacy compatibility for tests/mocks that return only HTML string.
        html, http_status, fetch_error = fetch_result, 200 if fetch_result else None, None
    if fetch_error:
        return _to_structured_error(
            platform,
            status=ParseListingStatusEnum.transient_error,
            reason="network_error",
            error="Не удалось загрузить страницу объявления. Повторите запрос позже.",
            action_required="retry_request",
        )
    if http_status in {403, 429}:
        return _to_structured_error(
            platform,
            status=ParseListingStatusEnum.blocked,
            reason=f"http_{http_status}",
            error="Площадка временно ограничила доступ к странице.",
            action_required="retry_later_or_proxy",
        )
    if not html:
        return _to_structured_error(
            platform,
            status=ParseListingStatusEnum.failed,
            reason="empty_response",
            error="Пустой ответ от площадки. Попробуйте позже или введите данные вручную.",
            action_required="fill_manual",
        )
    if _looks_blocked(html):
        return _to_structured_error(
            platform,
            status=ParseListingStatusEnum.blocked,
            reason="blocked_markup_detected",
            error="Площадка запросила защитную проверку (captcha/anti-bot).",
            action_required="retry_later_or_proxy",
        )

    soup = BeautifulSoup(html, "lxml")
    if platform == "avito":
        return _parse_avito(soup, url)
    if platform == "auto.ru":
        return _parse_auto_ru(soup, url)
    if platform == "drom":
        return _parse_drom(soup, url)
    if platform == "youla":
        return _parse_youla(soup, url)

    title_el = soup.select_one("h1")
    title = title_el.get_text(strip=True) if title_el else None
    brand, model = _split_brand_model(title or "")
    return ParsedListing(
        platform=platform,
        raw_title=title,
        vehicle=VehicleInput(brand=brand, model=model),
        parse_ok=bool(title),
        parse_status=(
            ParseListingStatusEnum.success.value
            if title
            else ParseListingStatusEnum.invalid_html.value
        ),
         parse_reason=None if title else "title_not_found",
        action_required=None if title else "fill_manual",
        parse_error=None if title else "Could not extract listing title.",
    )
