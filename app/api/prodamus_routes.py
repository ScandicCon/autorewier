"""Маршруты приёма оплаты через Prodamus.

- POST /payments/prodamus/subscribe — создаёт счёт (Payment) на Pro и возвращает
  ссылку на оплату. id счёта = order_id.
- POST /payments/prodamus/buy-pack — то же для пакета VIN-проверок.
- POST /payments/prodamus/webhook — уведомление об оплате: проверяем подпись и
  сумму, активируем Pro / начисляем кредиты, отвечаем 200.

Идемпотентность — через ProcessedWebhookEvent (повторные уведомления безопасны).
Бизнес-логика переиспользуется из subscription.py (как в robokassa_routes.py).
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Request
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
from app.security.rate_limit import enforce_rate_limit
from app.services import prodamus
from app.services.analytics import track_event
from app.services.subscription import (
    REPORT_PACKS,
    activate_pro_subscription,
    add_report_credits,
)

router = APIRouter()


@router.post("/payments/prodamus/subscribe")
async def prodamus_subscribe(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Создаёт счёт на Pro и возвращает ссылку на оплату Prodamus."""
    if not prodamus.is_configured():
        raise HTTPException(status_code=503, detail="Prodamus не настроен")
    await enforce_rate_limit(
        request,
        scope="api_subscribe",
        limit=settings.rate_limit_payment_limit,
        window_seconds=settings.rate_limit_payment_window_seconds,
        identity=str(user.id),
    )

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

    url = prodamus.build_payment_url(
        order_id=payment.id,
        amount_rub=amount,
        description="ПОДКАПОТ Pro — 30 дней",
        customer_email=user.email,
    )
    await track_event("payment_create", user_id=user.id, props={"provider": "prodamus"})
    return {"confirmation_url": url, "payment_id": payment.id}


@router.post("/payments/prodamus/buy-pack")
async def prodamus_buy_pack(
    request: Request,
    pack_size: int = Body(..., embed=True),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Создаёт счёт на пакет VIN-проверок и возвращает ссылку на оплату Prodamus."""
    if not prodamus.is_configured():
        raise HTTPException(status_code=503, detail="Prodamus не настроен")
    await enforce_rate_limit(
        request,
        scope="api_subscribe",
        limit=settings.rate_limit_payment_limit,
        window_seconds=settings.rate_limit_payment_window_seconds,
        identity=str(user.id),
    )

    price = REPORT_PACKS.get(pack_size)
    if price is None:
        raise HTTPException(status_code=400, detail="Неизвестный пакет")

    payment = Payment(
        user_id=user.id,
        amount_rub=price,
        plan=SubscriptionPlan.FREE,
        product="report_pack",
        report_credits=pack_size,
        status=PaymentStatus.PENDING,
    )
    session.add(payment)
    await session.commit()
    await session.refresh(payment)

    url = prodamus.build_payment_url(
        order_id=payment.id,
        amount_rub=price,
        description=f"ПОДКАПОТ — пакет {pack_size} проверок по VIN",
        customer_email=user.email,
    )
    await track_event(
        "report_pack_create",
        user_id=user.id,
        props={"provider": "prodamus", "pack": pack_size},
    )
    return {"confirmation_url": url, "payment_id": payment.id}


@router.api_route("/payments/prodamus/webhook", methods=["POST"])
async def prodamus_webhook(request: Request, session: AsyncSession = Depends(get_db)):
    """Уведомление об оплате от Prodamus."""
    await enforce_rate_limit(
        request,
        scope="prodamus_webhook",
        limit=settings.rate_limit_webhook_limit,
        window_seconds=settings.rate_limit_webhook_window_seconds,
    )

    # Данные приходят form-encoded; подпись — в заголовке Sign или в теле.
    data: dict = dict(request.query_params)
    try:
        form = await request.form()
        data.update({k: str(v) for k, v in form.items()})
    except Exception:  # noqa: BLE001 — тело может быть пустым/иным
        pass

    signature = (
        request.headers.get("Sign")
        or request.headers.get("sign")
        or data.get("signature")
        or data.get("sign")
    )
    if not prodamus.verify_webhook_signature(data, signature):
        raise HTTPException(status_code=400, detail="Invalid signature")

    order_id = data.get("order_id") or data.get("order_num")
    if not order_id or not str(order_id).isdigit():
        raise HTTPException(status_code=400, detail="Missing order_id")

    if not prodamus.is_success_payload(data):
        # Неуспех/ожидание — просто подтверждаем приём, доступ не выдаём.
        return PlainTextResponse("OK")

    # Идемпотентность: повторное уведомление по тому же счёту безопасно.
    marker = ProcessedWebhookEvent(
        provider="prodamus",
        event_key=f"prodamus:webhook:{order_id}",
        payload=data,
    )
    session.add(marker)
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        return PlainTextResponse("OK")

    payment = (
        await session.execute(select(Payment).where(Payment.id == int(order_id)))
    ).scalar_one_or_none()

    if payment and payment.status != PaymentStatus.SUCCEEDED:
        # Сверяем сумму: защита от занижения суммы в ссылке.
        try:
            paid = int(float(data.get("sum") or data.get("order_sum") or 0))
        except (TypeError, ValueError):
            paid = 0
        if paid and paid != payment.amount_rub:
            await session.commit()
            raise HTTPException(status_code=400, detail="Amount mismatch")

        payment.status = PaymentStatus.SUCCEEDED
        user = (
            await session.execute(select(User).where(User.id == payment.user_id))
        ).scalar_one_or_none()
        if user:
            if payment.product == "report_pack":
                add_report_credits(user, payment.report_credits)
            else:
                await activate_pro_subscription(session, user)

    await session.commit()
    return PlainTextResponse("OK")
