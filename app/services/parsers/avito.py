import json
import re
from urllib.parse import urlparse

from bs4 import BeautifulSoup

from app.schemas import VehicleInput
from app.services.listing_text import extract_listing_repairs
from app.services.parsers.avito_description import extract_avito_description
from app.services.parsers.avito_fetch import (
    AvitoFetchResult,
    AvitoFetchStatus,
    detect_block_state,
    fetch_avito_html,
    is_blocked_html,
    is_valid_listing_html,
    normalize_avito_url,
)
from app.services.parsers.base import (
    ParsedListing,
    _parse_int,
    _split_brand_model,
)

_MOJIBAKE_CHARS = ("Ð", "Ñ", "Â")


def is_avito_url(url: str) -> bool:
    host = urlparse(url.strip()).netloc.lower()
    return "avito.ru" in host


def _avito_item_id(url: str) -> str | None:
    m = re.search(r"_(\d{6,})", url) or re.search(r"/(\d{6,})(?:\?|$)", url)
    return m.group(1) if m else None


def _decode_unicode_json(text: str) -> str:
    try:
        decoded = json.loads(f'"{text}"')
    except json.JSONDecodeError:
        decoded = text.replace("\\n", "\n").replace('\\"', '"')
    return _repair_text(decoded)


def _text_quality_score(text: str) -> int:
    cyrillic = sum(1 for ch in text if ("а" <= ch.lower() <= "я") or ch in ("ё", "Ё"))
    mojibake = sum(text.count(ch) for ch in _MOJIBAKE_CHARS)
    return (cyrillic * 3) - (mojibake * 2)


def _repair_text(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.replace("\xa0", " ").strip()
    if not text:
        return text
    if sum(text.count(ch) for ch in _MOJIBAKE_CHARS) < 2:
        return text

    candidates = [text]
    for encoding in ("latin1", "cp1252"):
        try:
            candidates.append(text.encode(encoding).decode("utf-8"))
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue

    best = max(candidates, key=_text_quality_score)
    if _text_quality_score(best) > _text_quality_score(text):
        return best
    return text


def _from_json_ld(soup: BeautifulSoup) -> dict:
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
            if item.get("@type") in ("Product", "Car", "Vehicle", "Offer"):
                return item
            offers = item.get("offers") or {}
            if isinstance(offers, dict) and offers.get("price"):
                return {**item, "price": offers.get("price")}
    return {}


def _from_preloaded_state(html: str) -> dict:
    """Данные из большого JSON Avito в script."""
    found: dict = {}
    for marker in ("__preloadedState__", "__initialData__", '"catalog"'):
        idx = html.find(marker)
        if idx < 0:
            continue
        chunk = html[idx : idx + 500000]
        for key, pat in [
            ("title", r'"title"\s*:\s*"((?:\\.|[^"\\]){5,200})"'),
            ("description", r'"description"\s*:\s*"((?:\\.|[^"\\]){20,8000})"'),
            ("price", r'"price"\s*:\s*(\d{4,9})'),
            ("year", r'"year"\s*:\s*(\d{4})'),
            ("mileage", r'"mileage"\s*:\s*"?(\d{3,7})"?'),
        ]:
            if key in found:
                continue
            m = re.search(pat, chunk)
            if m:
                val = m.group(1)
                found[key] = _decode_unicode_json(val) if key != "price" else int(val)
    return found


def _from_embedded_scripts(html: str) -> dict:
    found: dict = _from_preloaded_state(html)
    patterns = [
        r'"title"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'"description"\s*:\s*"((?:\\.|[^"\\])*)"',
        r'"price"\s*:\s*(\d+)',
        r'"year"\s*:\s*(\d{4})',
        r'"mileage"\s*:\s*"?(\d+)"?',
    ]
    keys = ["title", "description", "price", "year", "mileage"]
    for key, pat in zip(keys, patterns):
        m = re.search(pat, html)
        if m:
            val = m.group(1)
            found[key] = _decode_unicode_json(val) if key != "price" else int(val)
    return found


def _parse_params(soup: BeautifulSoup) -> dict[str, str]:
    params: dict[str, str] = {}
    selectors = [
        '[data-marker="item-view/item-params"] li',
        '[data-marker="item-params/list"] li',
        ".params-paramsList li",
        ".item-params li",
        '[data-marker="item-params"] dd',
    ]
    for sel in selectors:
        for row in soup.select(sel):
            text = _repair_text(row.get_text(" ", strip=True)) or ""
            if ":" in text:
                k, v = text.split(":", 1)
                key = (_repair_text(k.strip()) or "").lower()
                params[key] = _repair_text(v.strip()) or ""
            elif len(text) > 3:
                parts = text.split(maxsplit=1)
                if len(parts) == 2:
                    key = (_repair_text(parts[0].strip()) or "").lower()
                    val = _repair_text(parts[1].strip()) or ""
                    params[key] = val
    for dl in soup.select("dl"):
        dts = dl.select("dt")
        dds = dl.select("dd")
        for dt, dd in zip(dts, dds):
            key = (_repair_text(dt.get_text(strip=True)) or "").lower()
            val = _repair_text(dd.get_text(strip=True)) or ""
            params[key] = val
    return params


def _extract_avito_photo_urls(soup: BeautifulSoup, html: str) -> list[str]:
    """Извлекает URL фотографий из галереи Avito."""
    photo_urls: list[str] = []
    seen: set[str] = set()

    # Галерея Avito: data-marker="image-frame/image"
    for img in soup.select(
        '[data-marker="image-frame/image"], '
        '[data-marker="item-view/gallery"] img, '
        '[data-marker="gallery-image"] img'
    ):
        for attr in ("src", "data-src", "data-original"):
            src = img.get(attr, "")
            if src and src.startswith("http") and src not in seen:
                seen.add(src)
                photo_urls.append(src)

    # JSON в <script> — ищем массив images/photos
    import re as _re
    for pat in (
        r'"images"\s*:\s*\[(.*?)\]',
        r'"photos"\s*:\s*\[(.*?)\]',
        r'"imageUrls"\s*:\s*\[(.*?)\]',
    ):
        m = _re.search(pat, html, _re.DOTALL)
        if m:
            chunk = m.group(1)
            for url_match in _re.finditer(r'"(https?://[^"]+\.(jpg|jpeg|png|webp)[^"]*)"', chunk):
                u = url_match.group(1)
                if u not in seen:
                    seen.add(u)
                    photo_urls.append(u)

    # og:image meta
    for meta in soup.select('meta[property="og:image"], meta[name="og:image"]'):
        content = meta.get("content", "")
        if content and content.startswith("http") and content not in seen:
            seen.add(content)
            photo_urls.append(content)

    return photo_urls[:30]


def _parse_avito_html(html: str, url: str) -> ParsedListing:
    soup = BeautifulSoup(html, "lxml")
    embedded = _from_embedded_scripts(html)
    json_ld = _from_json_ld(soup)

    title_el = soup.select_one('h1[data-marker="item-view/title-info"]') or soup.select_one("h1")
    title = (
        _repair_text(title_el.get_text(strip=True) if title_el else None)
        or _repair_text(embedded.get("title") if isinstance(embedded.get("title"), str) else None)
        or (_repair_text(str(json_ld.get("name"))) if json_ld.get("name") else None)
    )
    brand, model = _split_brand_model(str(title or ""))

    price_el = (
        soup.select_one('[data-marker="item-view/item-price"]')
        or soup.select_one('[itemprop="price"]')
        or soup.select_one('[data-marker="item-price"]')
    )
    price = None
    if price_el:
        if price_el.name == "meta":
            price = _parse_int(price_el.get("content"))
        else:
            price = _parse_int(price_el.get_text())
    if not price:
        price = embedded.get("price") or _parse_int(str(json_ld.get("offers", {}).get("price", "")))
        if not price and json_ld.get("price"):
            price = _parse_int(str(json_ld["price"]))

    params = _parse_params(soup)
    year = _parse_int(
        params.get("год выпуска")
        or params.get("год")
        or str(embedded.get("year", ""))
    )
    mileage = _parse_int(
        params.get("пробег") or params.get("пробег, км") or str(embedded.get("mileage", ""))
    )
    engine = params.get("двигатель") or params.get("объём двигателя") or params.get("объем двигателя")
    transmission = params.get("коробка передач") or params.get("кпп") or params.get("коробка")
    drive = params.get("привод")
    body = params.get("тип кузова") or params.get("кузов")
    color = params.get("цвет")

    description = _repair_text(extract_avito_description(html))
    if not description:
        desc_el = (
            soup.select_one('[data-marker="item-view/item-description"]')
            or soup.select_one('[data-marker="item-view/description"]')
            or soup.select_one('[itemprop="description"]')
        )
        if desc_el:
            description = _repair_text(desc_el.get_text("\n", strip=True))
    if not description:
        emb = embedded.get("description")
        if isinstance(emb, str) and len(emb) > 20:
            description = _repair_text(emb)
        elif json_ld.get("description"):
            description = _repair_text(str(json_ld.get("description")))

    repairs = extract_listing_repairs(description)
    photo_urls = _extract_avito_photo_urls(soup, html)
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
        and (price or year or mileage or (description and len(description) > 30))
    )
    error = None
    if not parse_ok:
        error = (
            "Не удалось извлечь поля из страницы Avito. "
            "Проверьте ссылку или введите данные вручную."
        )

    return ParsedListing(
        platform="avito",
        raw_title=title,
        vehicle=vehicle,
        parse_ok=parse_ok,
        parse_error=error,
        listing_repairs=repairs,
        photo_urls=photo_urls,
    )


def _normalize_fetch_result(raw_result: object) -> AvitoFetchResult:
    """
    Keep parser resilient while legacy call sites/tests still mock old tuple shape.
    Supported legacy shape: (html, error_message).
    """
    if isinstance(raw_result, AvitoFetchResult):
        return raw_result
    if isinstance(raw_result, tuple):
        html = raw_result[0] if len(raw_result) > 0 else None
        error = raw_result[1] if len(raw_result) > 1 else None
        html_value = html if isinstance(html, str) else None
        error_value = error if isinstance(error, str) else None
        detected, reason = detect_block_state(html_value)
        if detected:
            action_required = (
                "solve_captcha"
                if detected == AvitoFetchStatus.captcha
                else "retry_later_or_proxy"
                if detected == AvitoFetchStatus.blocked
                else "retry_request"
            )
            return AvitoFetchResult(
                html=html_value,
                status=detected,
                reason=reason,
                user_message=error_value,
                action_required=action_required,
            )
        if html_value:
            return AvitoFetchResult(
                html=html_value,
                status=AvitoFetchStatus.success,
                user_message=error_value,
            )
        return AvitoFetchResult(
            html=None,
            status=AvitoFetchStatus.failed,
            reason="legacy_fetch_result_empty",
            user_message=error_value or "Avito не загрузился. Введите данные вручную.",
            action_required="fill_manual",
        )
    return AvitoFetchResult(
        html=None,
        status=AvitoFetchStatus.failed,
        reason=f"unexpected_fetch_result:{type(raw_result).__name__}",
        user_message="Avito не загрузился. Введите данные вручную.",
        action_required="fill_manual",
    )


async def parse_avito_url(url: str) -> ParsedListing:
    if not is_avito_url(url):
        return ParsedListing(
            platform="avito",
            vehicle=VehicleInput(),
            parse_ok=False,
            parse_error="Нужна ссылка на avito.ru",
            parse_status=AvitoFetchStatus.failed.value,
            parse_reason="invalid_url",
            action_required="provide_avito_url",
        )

    canonical = normalize_avito_url(url)
    raw_fetch_result = await fetch_avito_html(canonical)
    fetch_result = _normalize_fetch_result(raw_fetch_result)
    html = fetch_result.html

    if not html:
        fallback_reason = fetch_result.reason or (
            "captcha_challenge"
            if fetch_result.status == AvitoFetchStatus.captcha
            else "access_blocked"
            if fetch_result.status == AvitoFetchStatus.blocked
            else "fetch_failed"
        )
        fallback_action = fetch_result.action_required or (
            "solve_captcha"
            if fetch_result.status == AvitoFetchStatus.captcha
            else "retry_later_or_proxy"
            if fetch_result.status == AvitoFetchStatus.blocked
            else "fill_manual"
        )
        return ParsedListing(
            platform="avito",
            vehicle=VehicleInput(),
            parse_ok=False,
            parse_error=fetch_result.user_message or "Сайт Avito не ответил.",
            parse_status=fetch_result.status.value,
            parse_reason=fallback_reason,
            action_required=fallback_action,
        )


    if is_blocked_html(html):
        blocked_status, blocked_reason = detect_block_state(html)
        status = blocked_status or AvitoFetchStatus.captcha
        if status == AvitoFetchStatus.captcha:
            blocked_message = "Avito captcha detected. Restart server or enter data manually."
        else:
            blocked_message = "Avito restricted access. Retry later or enter data manually."
        return ParsedListing(
            platform="avito",
            vehicle=VehicleInput(),
            parse_ok=False,
            parse_error=fetch_result.user_message or blocked_message,
            parse_status=status.value,
            parse_reason=blocked_reason or "blocked_page",
            action_required=(
                "solve_captcha" if status == AvitoFetchStatus.captcha else "retry_later_or_proxy"
            ),
        )

    if not is_valid_listing_html(html):
        return ParsedListing(
            platform="avito",
            vehicle=VehicleInput(),
            parse_ok=False,
            parse_error="Avito page loaded partially. Retry or enter data manually.",
            parse_status=AvitoFetchStatus.invalid_html.value,
            parse_reason="listing_markup_not_detected",
            action_required="retry_request",
        )

    result = _parse_avito_html(html, canonical)
    result.parse_status = AvitoFetchStatus.success.value
    result.parse_reason = fetch_result.reason
    result.action_required = None
    if not result.parse_ok:
        result.parse_error = result.parse_error or fetch_result.user_message
        result.parse_status = AvitoFetchStatus.invalid_html.value
        result.parse_reason = "fields_not_extracted"
        result.action_required = "fill_manual"
    return result
