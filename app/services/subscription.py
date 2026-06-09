import base64
import uuid
from datetime import datetime, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Payment, PaymentStatus, ProcessedWebhookEvent, SubscriptionPlan, User


def current_month_key() -> str:
    return datetime.now().strftime("%Y-%m")


def is_pro_active(user: User) -> bool:
    if user.subscription_plan == SubscriptionPlan.PRO and user.subscription_until:
        return user.subscription_until > datetime.now()
    return False


def _reset_month_counter(user: User) -> None:
    key = current_month_key()
    if user.month_reset_key != key:
        user.month_reset_key = key
        user.inspections_this_month = 0


def can_create_inspection(user: User) -> tuple[bool, str]:
    _reset_month_counter(user)
    if is_pro_active(user):
        return True, ""
    if user.inspections_this_month >= settings.free_inspections_per_month:
        return (
            False,
            f"Лимит бесплатного тарифа: {settings.free_inspections_per_month} проверок в месяц. "
            "Оформите подписку Pro.",
        )
    return True, ""


def increment_inspection_usage(user: User) -> None:
    _reset_month_counter(user)
    if not is_pro_active(user):
        user.inspections_this_month += 1


async def create_yookassa_payment(session: AsyncSession, user: User) -> dict:
    if not settings.yookassa_enabled:
        raise RuntimeError("ЮKassa не настроена")

    payment = Payment(
        user_id=user.id,
        amount_rub=settings.subscription_pro_price_rub,
        plan=SubscriptionPlan.PRO,
        status=PaymentStatus.PENDING,
    )
    session.add(payment)
    await session.flush()

    idempotence_key = str(uuid.uuid4())
    auth = base64.b64encode(
        f"{settings.yookassa_shop_id}:{settings.yookassa_secret_key}".encode()
    ).decode()

    body = {
        "amount": {"value": f"{settings.subscription_pro_price_rub:.2f}", "currency": "RUB"},
        "confirmation": {
            "type": "redirect",
            "return_url": settings.yookassa_return_url,
        },
        "capture": True,
        "description": "AutoRewier Pro — 30 дней",
        "metadata": {"user_id": str(user.id), "payment_id": str(payment.id)},
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(
            "https://api.yookassa.ru/v3/payments",
            json=body,
            headers={
                "Authorization": f"Basic {auth}",
                "Idempotence-Key": idempotence_key,
                "Content-Type": "application/json",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    payment.yookassa_payment_id = data["id"]
    await session.commit()

    return {
        "payment_id": payment.id,
        "confirmation_url": data["confirmation"]["confirmation_url"],
    }


async def activate_pro_subscription(session: AsyncSession, user: User) -> None:
    now = datetime.now()
    base = user.subscription_until if user.subscription_until and user.subscription_until > now else now
    user.subscription_plan = SubscriptionPlan.PRO
    user.subscription_until = base + timedelta(days=30)
    await session.commit()


async def _fetch_yookassa_payment(payment_id: str) -> dict:
    auth = base64.b64encode(
        f"{settings.yookassa_shop_id}:{settings.yookassa_secret_key}".encode()
    ).decode()
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.get(
            f"https://api.yookassa.ru/v3/payments/{payment_id}",
            headers={"Authorization": f"Basic {auth}"},
        )
        resp.raise_for_status()
        return resp.json()


async def handle_yookassa_webhook(session: AsyncSession, payload: dict) -> bool:
    event = payload.get("event")
    obj = payload.get("object") or {}
    if event != "payment.succeeded":
        return False

    yid = obj.get("id")
    if not yid:
        return False

    event_key = f"yookassa:{event}:{yid}:{obj.get('status', '')}"
    marker = ProcessedWebhookEvent(
        provider="yookassa",
        event_key=event_key,
        payload=payload,
    )
    session.add(marker)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return False

    result = await session.execute(
        select(Payment).where(Payment.yookassa_payment_id == yid)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        await session.commit()
        return False

    if payment.status == PaymentStatus.SUCCEEDED:
        await session.commit()
        return False

    if settings.yookassa_enabled:
        payment_state = await _fetch_yookassa_payment(yid)
        if payment_state.get("status") != "succeeded":
            await session.commit()
            return False
        amount_value = int(float(payment_state.get("amount", {}).get("value", "0")))
        if amount_value != payment.amount_rub:
            await session.commit()
            return False
    elif settings.is_production:
        await session.commit()
        return False

    payment.status = PaymentStatus.SUCCEEDED
    user = await session.get(User, payment.user_id)
    if user:
        now = datetime.now()
        base = user.subscription_until if user.subscription_until and user.subscription_until > now else now
        user.subscription_plan = SubscriptionPlan.PRO
        user.subscription_until = base + timedelta(days=30)
    await session.commit()
    return True
