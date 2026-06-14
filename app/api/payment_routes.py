import json

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.security.rate_limit import enforce_rate_limit
from app.security.yookassa import verify_yookassa_source_ip
from app.services.analytics import track_event
from app.services.subscription import (
    REPORT_PACKS,
    can_use_vin_report,
    create_report_pack_payment,
    create_yookassa_payment,
    handle_yookassa_webhook,
    is_pro_active,
)

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


class BuyReportPackRequest(BaseModel):
    pack_size: int


@router.get("/report-packs")
async def report_packs(
    user: User = Depends(get_current_user),
):
    """Доступные пакеты VIN-отчётов и текущий остаток квоты пользователя."""
    from app.config import settings

    included = settings.pro_vin_reports_included if is_pro_active(user) else 0
    used = user.vin_reports_this_month or 0
    quota_left = max(0, included - used) if is_pro_active(user) else 0
    return {
        "packs": [{"pack_size": k, "price_rub": v} for k, v in sorted(REPORT_PACKS.items())],
        "is_pro": is_pro_active(user),
        "included_per_month": included,
        "quota_left": quota_left,
        "report_credits": user.report_credits or 0,
    }


@router.post("/buy-report-pack")
async def buy_report_pack(
    body: BuyReportPackRequest,
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
        raise HTTPException(503, "Оплата не настроена.")
    try:
        data = await create_report_pack_payment(session, user, body.pack_size)
        await track_event("report_pack_create", user_id=user.id, props={"pack": body.pack_size})
        return data
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        raise HTTPException(502, str(e)) from e


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
