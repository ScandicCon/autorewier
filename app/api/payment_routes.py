import json

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.security.rate_limit import enforce_rate_limit
from app.security.yookassa import verify_yookassa_source_ip
from app.services.analytics import track_event
from app.services.subscription import create_yookassa_payment, handle_yookassa_webhook

router = APIRouter(prefix="/payments", tags=["payments"])


@router.post("/subscribe")
async def subscribe(
    request: Request,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="api_subscribe",
        limit=settings.rate_limit_payment_limit,
        window_seconds=settings.rate_limit_payment_window_seconds,
        identity=str(user.id),
    )
    if not settings.yookassa_enabled:
        raise HTTPException(
            503,
            "Оплата не настроена. Укажите YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY в .env",
        )
    try:
        data = await create_yookassa_payment(session, user)
        await track_event("payment_create", user_id=user.id, props={"origin": "api"})
        return data
    except Exception as e:
        raise HTTPException(502, str(e)) from e


@router.post("/webhook/yookassa")
async def yookassa_webhook(request: Request, session: AsyncSession = Depends(get_db)):
    await enforce_rate_limit(
        request,
        scope="yookassa_webhook",
        limit=settings.rate_limit_webhook_limit,
        window_seconds=settings.rate_limit_webhook_window_seconds,
    )
    source_ip = verify_yookassa_source_ip(request)
    raw_body = await request.body()
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(400, "Invalid webhook payload") from exc
    processed = await handle_yookassa_webhook(session, payload)
    if processed:
        await track_event("payment_webhook_processed", props={"source_ip": source_ip})
    return {"ok": True}


@router.post("/dev/activate-pro")
async def dev_activate_pro(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Только для локальной разработки без ЮKassa."""
    if not settings.can_use_dev_payment_bypass:
        raise HTTPException(403, "Dev activation is disabled")
    from app.services.subscription import activate_pro_subscription

    await activate_pro_subscription(session, user)
    return {"ok": True, "plan": "pro"}
