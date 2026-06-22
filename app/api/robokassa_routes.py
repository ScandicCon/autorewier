"""Маршруты приёма оплаты через Robokassa.

- POST /payments/robokassa/subscribe — создаёт счёт (Payment) и возвращает URL
  для перенаправления покупателя на оплату. id счёта используется как InvId.
- GET|POST /payments/robokassa/result — ResultURL: Robokassa уведомляет об оплате.
  Проверяем подпись (Password2), активируем Pro, отвечаем "OK{InvId}".

Идемпотентность — через ProcessedWebhookEvent (повторные уведомления безопасны).
Ключи Robokassa читаются из окружения (см. app/services/robokassa.py).
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import PlainTextResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import (
    Payment,
    PaymentStatus,
    ProcessedWebhookEvent,
    SubscriptionPlan,
    User,
)
from app.services import robokassa
from app.services.analytics import track_event
from app.services.subscription import activate_pro_subscription

router = APIRouter()


@router.post("/payments/robokassa/subscribe")
async def robokassa_subscribe(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Создаёт счёт на Pro и возвращает ссылку на оплату Robokassa."""
    if not robokassa.is_configured():
        raise HTTPException(status_code=503, detail="Robokassa не настроена")

    amount = settings.subscription_pro_price_rub
    payment = Payment(
        user_id=user.id,
        amount_rub=amount,
        plan=SubscriptionPlan.PRO,
        product="subscription",
        status=PaymentStatus.PENDING,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)

    url = robokassa.build_payment_url(
        out_sum=f"{amount}.00",
        inv_id=payment.id,
        description="AutoRewier Pro — 30 дней",
        shp={"Shp_user": user.id},
        email=user.email,
    )
    await track_event("payment_create", user_id=user.id, props={"provider": "robokassa"})
    return {"payment_url": url, "inv_id": payment.id}


def _collect_params(data: dict) -> tuple[str | None, str | None, str | None, dict]:
    out_sum = data.get("OutSum") or data.get("outSum")
    inv_id = data.get("InvId") or data.get("invId")
    signature = data.get("SignatureValue") or data.get("signatureValue")
    shp = {k: v for k, v in data.items() if k.lower().startswith("shp_")}
    return out_sum, inv_id, signature, shp


@router.api_route("/payments/robokassa/result", methods=["GET", "POST"])
async def robokassa_result(request: Request, session: AsyncSession = Depends(get_db)):
    """ResultURL: подтверждение оплаты от Robokassa."""
    data: dict = dict(request.query_params)
    if request.method == "POST":
        form = await request.form()
        data.update({k: str(v) for k, v in form.items()})

    out_sum, inv_id, signature, shp = _collect_params(data)
    if not (out_sum and inv_id and signature):
        raise HTTPException(status_code=400, detail="Missing parameters")

    if not robokassa.verify_result_signature(out_sum, inv_id, signature, shp=shp or None):
        raise HTTPException(status_code=400, detail="Invalid signature")

    # Идемпотентность: повторное уведомление по тому же счёту не активирует Pro дважды.
    marker = ProcessedWebhookEvent(
        provider="robokassa",
        event_key=f"robokassa:result:{inv_id}",
        payload=data,
    )
    session.add(marker)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return PlainTextResponse(robokassa.success_response(inv_id))

    payment = (
        await session.execute(select(Payment).where(Payment.id == int(inv_id)))
    ).scalar_one_or_none()

    if payment and payment.status != PaymentStatus.SUCCEEDED:
        payment.status = PaymentStatus.SUCCEEDED
        user = (
            await session.execute(select(User).where(User.id == payment.user_id))
        ).scalar_one_or_none()
        if user and payment.product == "subscription":
            await activate_pro_subscription(session, user)

    await session.commit()
    return PlainTextResponse(robokassa.success_response(inv_id))
