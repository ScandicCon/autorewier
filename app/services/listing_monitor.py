"""Мониторинг объявлений: отслеживание изменений цены и статуса."""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models import ChangeType, ListingChangeEvent, ListingStatus, MonitoredListing
from app.services.parsers.base import _detect_platform

logger = logging.getLogger("autorewier.listing_monitor")


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def check_listing_status(url: str) -> dict:
    """Парсит страницу объявления и возвращает текущее состояние.

    Returns:
        dict с ключами: price (int|None), status ("active"|"sold"|"removed"),
        title (str|None).
    """
    from app.services.parsers.base import _fetch_html, _looks_blocked
    from bs4 import BeautifulSoup

    result: dict = {
        "price": None,
        "status": "active",
        "title": None,
    }

    try:
        html, http_status, error = await _fetch_html(url)
    except Exception as exc:
        logger.warning("listing_monitor_fetch_failed", extra={"url": url, "error": str(exc)})
        return result

    if error or not html:
        return result

    if http_status == 404:
        result["status"] = "removed"
        return result

    if http_status in (403, 429):
        logger.info("listing_monitor_blocked", extra={"url": url, "status": http_status})
        return result

    if _looks_blocked(html):
        return result

    soup = BeautifulSoup(html, "lxml")

    # Определяем платформу и парсим соответственно
    platform = _detect_platform(url)

    # Попытка найти признак продажи/снятия
    page_text = html.lower()
    sold_markers = (
        "объявление снято",
        "объявление удалено",
        "объявление не найдено",
        "продано",
        "sold",
        "снято с продажи",
        "страница не найдена",
    )
    if any(m in page_text for m in sold_markers):
        result["status"] = "removed"
        return result

    # Заголовок
    h1 = soup.select_one("h1")
    result["title"] = h1.get_text(strip=True) if h1 else None

    # Цена — универсальные селекторы
    price_selectors = [
        '[data-marker="item-view/item-price"]',
        '[data-marker="item-price"]',
        '[itemprop="price"]',
        ".auto-price",
        '[data-field="price"]',
        '[data-ftid="bull_price"]',
        ".OfferPriceCaption__price",
    ]
    for sel in price_selectors:
        el = soup.select_one(sel)
        if el:
            from app.services.parsers.base import _parse_int
            if el.name == "meta":
                price = _parse_int(el.get("content"))
            else:
                price = _parse_int(el.get_text())
            if price:
                result["price"] = price
                break

    return result


async def run_monitoring_cycle() -> None:
    """Обходит все активные MonitoredListing, сравнивает с прошлым состоянием.

    При изменении цены или статуса создаёт ListingChangeEvent и отправляет
    Telegram-уведомление пользователю.
    """
    logger.info("monitoring_cycle_started")
    now = _now_utc()

    async with async_session() as session:
        result = await session.execute(
            select(MonitoredListing).where(MonitoredListing.is_active == True)  # noqa: E712
        )
        listings: list[MonitoredListing] = list(result.scalars().all())

    logger.info("monitoring_cycle_listings", extra={"count": len(listings)})

    for listing in listings:
        try:
            await _check_one(listing)
        except Exception as exc:
            logger.exception(
                "monitoring_cycle_item_failed",
                extra={"listing_id": listing.id, "error": str(exc)},
            )

    logger.info("monitoring_cycle_done")


async def _check_one(listing: MonitoredListing) -> None:
    """Проверяет одно объявление и сохраняет изменения."""
    now = _now_utc()
    current = await check_listing_status(listing.url)

    async with async_session() as session:
        # Перечитываем из сессии, чтобы не было detached instance
        db_listing = await session.get(MonitoredListing, listing.id)
        if not db_listing:
            return

        events_to_create: list[ListingChangeEvent] = []

        new_price = current.get("price")
        new_status_str = current.get("status", "active")
        new_status = ListingStatus(new_status_str) if new_status_str in ListingStatus.__members__.values() else ListingStatus.ACTIVE

        # Проверяем изменение цены
        if new_price and db_listing.last_price and new_price != db_listing.last_price:
            change_type = (
                ChangeType.PRICE_DROP
                if new_price < db_listing.last_price
                else ChangeType.PRICE_RISE
            )
            event = ListingChangeEvent(
                monitored_listing_id=db_listing.id,
                change_type=change_type,
                old_value=str(db_listing.last_price),
                new_value=str(new_price),
            )
            events_to_create.append(event)
            logger.info(
                "listing_price_changed",
                extra={
                    "listing_id": db_listing.id,
                    "old": db_listing.last_price,
                    "new": new_price,
                    "type": change_type.value,
                },
            )

        # Проверяем изменение статуса
        if new_status != db_listing.last_status:
            if new_status in (ListingStatus.SOLD, ListingStatus.REMOVED):
                change_type = (
                    ChangeType.SOLD
                    if new_status == ListingStatus.SOLD
                    else ChangeType.REMOVED
                )
                event = ListingChangeEvent(
                    monitored_listing_id=db_listing.id,
                    change_type=change_type,
                    old_value=db_listing.last_status.value,
                    new_value=new_status.value,
                )
                events_to_create.append(event)
                # Деактивируем мониторинг для снятых/проданных объявлений
                db_listing.is_active = False
                logger.info(
                    "listing_status_changed",
                    extra={
                        "listing_id": db_listing.id,
                        "old": db_listing.last_status.value,
                        "new": new_status.value,
                    },
                )

        # Обновляем поля
        if new_price:
            db_listing.last_price = new_price
        db_listing.last_status = new_status
        db_listing.last_checked_at = now

        for ev in events_to_create:
            session.add(ev)

        await session.commit()

        # Отправляем уведомления
        for ev in events_to_create:
            await session.refresh(ev)
            await _notify_user(listing.user_id, db_listing, ev)


async def _notify_user(
    user_id: int,
    listing: MonitoredListing,
    event: ListingChangeEvent,
) -> None:
    """Отправляет Telegram-уведомление об изменении объявления."""
    try:
        from app.bot.handlers import send_monitoring_notification
        await send_monitoring_notification(user_id, listing, event)
    except Exception as exc:
        logger.warning(
            "monitoring_notification_failed",
            extra={"user_id": user_id, "listing_id": listing.id, "error": str(exc)},
        )
