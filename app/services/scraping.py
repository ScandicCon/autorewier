"""Единый слой загрузки HTML с опциональным ScrapingBee.

Зачем: парсинг Авито — главный риск воронки (капча/блок на дата-центровых IP).
ScrapingBee — внешний скрейпинг-API: сам обходит антибот и при необходимости
рендерит страницу, возвращая готовый HTML. Этот модуль — тонкая обёртка с
мягкой деградацией, в духе всего проекта:

    есть SCRAPINGBEE_API_KEY  → грузим страницу через ScrapingBee;
    нет ключа / он не ответил  → обычный прямой httpx.

ВАЖНО: логика РАЗБОРА HTML (BeautifulSoup) остаётся у вызывающего кода без
изменений — здесь меняется только слой ЗАГРУЗКИ. Это позволяет постепенно
переключать парсеры на ScrapingBee, не переписывая их.

Модуль НЕ трогает существующий `parsers/avito_fetch.py` (Playwright). Он —
переиспользуемая точка, к которой при желании можно подключить и Avito-парсер.
"""
from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
SCRAPINGBEE_ENDPOINT = "https://app.scrapingbee.com/api/v1/"


async def fetch_html(
    url: str,
    *,
    timeout: float = 20.0,
    render_js: bool | None = None,
    premium_proxy: bool | None = None,
    country_code: str | None = None,
    user_agent: str = DEFAULT_USER_AGENT,
) -> str | None:
    """Загрузить HTML страницы. Через ScrapingBee, если задан ключ, иначе прямой httpx.

    Возвращает HTML-строку или None (страница недоступна/заблокирована) — вызывающий
    код сам решает, как деградировать (ручной ввод, пустой результат и т.д.).
    """
    if settings.scrapingbee_enabled:
        html = await _fetch_via_scrapingbee(
            url,
            timeout=timeout,
            render_js=render_js,
            premium_proxy=premium_proxy,
            country_code=country_code,
        )
        if html is not None:
            return html
        # ScrapingBee не ответил — пробуем напрямую, чтобы не терять запрос целиком.
        logger.warning("scrapingbee fetch failed for %s — fallback to direct httpx", url)

    return await _fetch_direct(url, timeout=timeout, user_agent=user_agent)


async def fetch_via_scrapingbee(
    url: str,
    *,
    timeout: float = 20.0,
    render_js: bool | None = None,
    premium_proxy: bool | None = None,
    country_code: str | None = None,
) -> str | None:
    """Загрузка ТОЛЬКО через ScrapingBee, без httpx-фолбэка.

    Зачем: fetch_html() при неудаче ScrapingBee падает на прямой httpx — для
    Avito это бессмысленно (прямой запрос с серверного IP уже был испробован
    и заблокирован). Этот публичный вход отдаёт None, если ключа нет или
    ScrapingBee не справился, — вызывающий код сам решает, как деградировать.
    """
    if not settings.scrapingbee_enabled:
        return None
    return await _fetch_via_scrapingbee(
        url,
        timeout=timeout,
        render_js=render_js,
        premium_proxy=premium_proxy,
        country_code=country_code,
    )


async def _fetch_via_scrapingbee(
    url: str,
    *,
    timeout: float,
    render_js: bool | None,
    premium_proxy: bool | None,
    country_code: str | None,
) -> str | None:
    if render_js is None:
        render_js = settings.scrapingbee_render_js
    if premium_proxy is None:
        premium_proxy = settings.scrapingbee_premium_proxy
    if country_code is None:
        country_code = settings.scrapingbee_country_code

    params: dict[str, str] = {
        "api_key": settings.scrapingbee_api_key.strip(),
        "url": url,
        "render_js": "true" if render_js else "false",
    }
    if premium_proxy:
        # Резидентные прокси нужны для тяжёлых антиботов (Avito). Дороже по кредитам.
        params["premium_proxy"] = "true"
        if country_code:
            params["country_code"] = country_code

    try:
        # ScrapingBee сам долго ждёт рендера — даём ему запас по таймауту.
        async with httpx.AsyncClient(timeout=timeout + 20.0) as client:
            resp = await client.get(SCRAPINGBEE_ENDPOINT, params=params)
            if resp.status_code == 200 and resp.text:
                # Учёт себестоимости: ScrapingBee возвращает потраченные
                # кредиты в заголовке Spb-cost.
                from app.services.cost_tracking import record_scrapingbee
                try:
                    headers = getattr(resp, "headers", {}) or {}
                    credits = int(
                        headers.get("Spb-cost") or headers.get("spb-cost") or 0
                    )
                except (TypeError, ValueError, AttributeError):
                    credits = 0
                record_scrapingbee(credits)
                return resp.text
            logger.warning(
                "scrapingbee returned status %s for %s", resp.status_code, url
            )
    except httpx.HTTPError as exc:
        logger.warning("scrapingbee request error for %s: %s", url, exc)
    return None


async def _fetch_direct(url: str, *, timeout: float, user_agent: str) -> str | None:
    try:
        async with httpx.AsyncClient(
            follow_redirects=True,
            timeout=timeout,
            headers={"User-Agent": user_agent},
        ) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                return resp.text
    except httpx.HTTPError:
        return None
    return None
