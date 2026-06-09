"""Парсер объявлений Drom.ru."""
from __future__ import annotations

import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.schemas import VehicleInput
from app.services.listing_text import extract_listing_repairs
from app.services.parsers.base import (
    ParsedListing,
    _fetch_html,
    _looks_blocked,
    _parse_int,
    _split_brand_model,
)
from app.schemas import ParseListingStatusEnum


def is_drom_url(url: str) -> bool:
    host = urlparse(url.strip()).netloc.lower()
    return "drom.ru" in host


def _extract_photo_urls(soup: BeautifulSoup) -> list[str]:
    """Извлекает URL фотографий из галереи объявления Drom."""
    photo_urls: list[str] = []
    seen: set[str] = set()

    # Галерея: data-attrs или og:image в meta
    for sel in (
        'img[data-src*="drom"]',
        'img[src*="drom"]',
        '[data-ftid="bull_image"] img',
        ".b-slider img",
        ".b-photo-gallery img",
        '[class*="photo"] img',
        '[class*="gallery"] img',
    ):
        for img in soup.select(sel):
            src = img.get("data-src") or img.get("src") or ""
            if src and src.startswith("http") and src not in seen:
                # Пропускаем иконки и маленькие превью
                if any(x in src for x in ("icon", "logo", "avatar", "placeholder")):
                    continue
                seen.add(src)
                photo_urls.append(src)

    # JSON-LD может содержать список фото
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
            images = item.get("image", [])
            if isinstance(images, str):
                images = [images]
            for img_url in images:
                if isinstance(img_url, str) and img_url.startswith("http") and img_url not in seen:
                    seen.add(img_url)
                    photo_urls.append(img_url)

    return photo_urls[:30]


def _parse_drom_html(html: str, url: str) -> ParsedListing:
    soup = BeautifulSoup(html, "lxml")

    title_el = (
        soup.select_one('h1[data-ftid="bull_title"]')
        or soup.select_one("h1.bull-item-title")
        or soup.select_one("h1")
    )
    title = title_el.get_text(strip=True) if title_el else None
    brand, model = _split_brand_model(title or "")

    # Цена
    price_el = (
        soup.select_one('[data-ftid="bull_price"]')
        or soup.select_one(".auto-price")
        or soup.select_one('[data-field="price"]')
        or soup.select_one('[itemprop="price"]')
        or soup.select_one(".b-list-advert-base-item__price")
    )
    price = None
    if price_el:
        if price_el.name == "meta":
            price = _parse_int(price_el.get("content"))
        else:
            price = _parse_int(price_el.get_text())

    # Параметры
    specs: dict[str, str] = {}
    for row in soup.select(
        "li, .css-1x4jcd6, tr.b-characteristics-items, .b-characteristics-value"
    ):
        text = row.get_text(" ", strip=True)
        if ":" in text:
            k, v = text.split(":", 1)
            key = k.strip().lower()
            val = v.strip()
            if key and val:
                specs[key] = val
    # dl-based tables (типичны для Drom)
    for dl in soup.select("dl"):
        dts = dl.select("dt")
        dds = dl.select("dd")
        for dt, dd in zip(dts, dds):
            key = dt.get_text(strip=True).lower()
            val = dd.get_text(strip=True)
            if key and val:
                specs[key] = val
    # table rows
    for tr in soup.select("table tr"):
        cells = tr.select("td, th")
        if len(cells) >= 2:
            key = cells[0].get_text(strip=True).lower()
            val = cells[1].get_text(strip=True)
            if key and val:
                specs[key] = val

    year = _parse_int(
        specs.get("год выпуска") or specs.get("год") or specs.get("year")
    )
    mileage = _parse_int(
        specs.get("пробег") or specs.get("пробег, км") or specs.get("mileage")
    )
    engine = specs.get("двигатель") or specs.get("engine") or specs.get("объём двигателя")
    transmission = specs.get("коробка передач") or specs.get("кпп")
    drive = specs.get("привод")
    body = specs.get("кузов") or specs.get("тип кузова")
    color = specs.get("цвет")

    # Описание
    desc_el = (
        soup.select_one('[data-ftid="bull_description"]')
        or soup.select_one('[itemprop="description"]')
        or soup.select_one(".b-media-cont_margin_t_20")
        or soup.select_one(".b-description")
    )
    description = desc_el.get_text("\n", strip=True) if desc_el else None

    # JSON-LD fallback
    if not (brand or model or price or year):
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
                if not title and item.get("name"):
                    title = str(item["name"])
                    brand, model = _split_brand_model(title)
                if not year and item.get("vehicleModelDate"):
                    year = _parse_int(str(item["vehicleModelDate"]))
                if not price:
                    offers = item.get("offers", {})
                    if isinstance(offers, dict):
                        price = _parse_int(str(offers.get("price", "")))
                    elif item.get("price"):
                        price = _parse_int(str(item["price"]))
                if not description and isinstance(item.get("description"), str):
                    description = item["description"]

    photo_urls = _extract_photo_urls(soup)
    repairs = extract_listing_repairs(description)

    vehicle = VehicleInput(
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
    )

    parse_ok = bool(
        (brand or model or title)
        and (price or year or mileage or (description and len(description) > 20))
    )
    error = None if parse_ok else (
        "Не удалось извлечь поля из страницы Drom. "
        "Проверьте ссылку или введите данные вручную."
    )

    return ParsedListing(
        platform="drom",
        raw_title=title,
        vehicle=vehicle,
        parse_ok=parse_ok,
        parse_error=error,
        parse_status=(
            ParseListingStatusEnum.success.value
            if parse_ok
            else ParseListingStatusEnum.invalid_html.value
        ),
        parse_reason=None if parse_ok else "drom_fields_not_extracted",
        action_required=None if parse_ok else "fill_manual",
        listing_repairs=repairs,
        photo_urls=photo_urls,
    )


async def parse_drom_url(url: str) -> ParsedListing:
    """Основная точка входа для парсинга объявлений Drom."""
    if not is_drom_url(url):
        return ParsedListing(
            platform="drom",
            vehicle=VehicleInput(),
            parse_ok=False,
            parse_error="Нужна ссылка на drom.ru",
            parse_status=ParseListingStatusEnum.failed.value,
            parse_reason="invalid_url",
            action_required="provide_drom_url",
        )

    html, http_status, error = await _fetch_html(url)

    if error:
        return ParsedListing(
            platform="drom",
            vehicle=VehicleInput(),
            parse_ok=False,
            parse_error="Не удалось загрузить страницу Drom. Попробуйте позже.",
            parse_status=ParseListingStatusEnum.transient_error.value,
            parse_reason="network_error",
            action_required="retry_request",
        )

    if http_status == 404 or not html:
        return ParsedListing(
            platform="drom",
            vehicle=VehicleInput(),
            parse_ok=False,
            parse_error="Объявление Drom не найдено или удалено.",
            parse_status=ParseListingStatusEnum.failed.value,
            parse_reason="not_found",
            action_required="fill_manual",
        )

    if http_status in (403, 429):
        return ParsedListing(
            platform="drom",
            vehicle=VehicleInput(),
            parse_ok=False,
            parse_error="Drom временно ограничил доступ. Повторите позже.",
            parse_status=ParseListingStatusEnum.blocked.value,
            parse_reason=f"http_{http_status}",
            action_required="retry_later_or_proxy",
        )

    if _looks_blocked(html):
        return ParsedListing(
            platform="drom",
            vehicle=VehicleInput(),
            parse_ok=False,
            parse_error="Drom запросил защитную проверку. Повторите позже.",
            parse_status=ParseListingStatusEnum.blocked.value,
            parse_reason="blocked_markup_detected",
            action_required="retry_later_or_proxy",
        )

    return _parse_drom_html(html, url)
