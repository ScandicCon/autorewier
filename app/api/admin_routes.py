from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.config import settings
from app.database import get_db
from app.models import Inspection, Payment, PaymentStatus, User
from app.schemas import AdminHealthResponse, AdminStatsResponse, AdminSupportStatusResponse
from app.services.task_queue import get_queue_depth

router = APIRouter(prefix="/admin", tags=["admin"])
support_router = APIRouter(prefix="/support", tags=["support"])


def require_admin_token(x_admin_token: str | None = Header(None, alias="X-Admin-Token")) -> None:
    if not settings.admin_api_token.strip():
        raise HTTPException(status_code=503, detail="Admin API token is not configured")
    if x_admin_token != settings.admin_api_token:
        raise HTTPException(status_code=403, detail="Forbidden")


@router.get("/health", response_model=AdminHealthResponse)
async def admin_health(
    _: None = Depends(require_admin_token),
    session: AsyncSession = Depends(get_db),
):
    await session.execute(text("SELECT 1"))
    queue_depth = await get_queue_depth()
    return {
        "ok": True,
        "version": __version__,
        "app_version": settings.app_version,
        "revision": settings.app_revision,
        "environment": settings.environment,
        "queue_enabled": settings.task_queue_enabled,
        "queue_depth": queue_depth,
        "db_ok": True,
    }


@router.get("/stats", response_model=AdminStatsResponse)
async def admin_stats(
    _: None = Depends(require_admin_token),
    session: AsyncSession = Depends(get_db),
):
    users_total = await session.scalar(select(func.count()).select_from(User))
    inspections_total = await session.scalar(select(func.count()).select_from(Inspection))
    payments_total = await session.scalar(select(func.count()).select_from(Payment))
    succeeded_payments = await session.scalar(
        select(func.count()).select_from(Payment).where(Payment.status == PaymentStatus.SUCCEEDED)
    )
    queue_depth = await get_queue_depth()
    # Себестоимость проверок (Фаза 0.4): агрегаты по сохранённой cost_rub.
    inspections_with_cost = await session.scalar(
        select(func.count()).select_from(Inspection).where(Inspection.cost_rub.isnot(None))
    )
    total_cost_rub = await session.scalar(select(func.sum(Inspection.cost_rub)))
    avg_cost_rub = await session.scalar(select(func.avg(Inspection.cost_rub)))
    return {
        "users_total": users_total or 0,
        "inspections_total": inspections_total or 0,
        "payments_total": payments_total or 0,
        "succeeded_payments": succeeded_payments or 0,
        "queue_depth": queue_depth,
        "inspections_with_cost": inspections_with_cost or 0,
        "total_cost_rub": round(total_cost_rub, 4) if total_cost_rub is not None else None,
        "avg_cost_rub": round(avg_cost_rub, 4) if avg_cost_rub is not None else None,
    }


@router.get("/support-status", response_model=AdminSupportStatusResponse)
async def admin_support_status(
    _: None = Depends(require_admin_token),
):
    return {
        "environment": settings.environment,
        "admin_auth_configured": bool(settings.admin_api_token.strip()),
        "rate_limit_enabled": settings.rate_limit_enabled,
        "trusted_proxy_hops": max(0, settings.trusted_proxy_hops),
        "trusted_proxy_cidrs": [
            value.strip() for value in settings.trusted_proxy_cidrs.split(",") if value.strip()
        ],
        "yookassa_enabled": settings.yookassa_enabled,
        "autocode_enabled": settings.autocode_enabled,
        "queue_enabled": bool(settings.task_queue_enabled and settings.redis_url.strip()),
    }


# ---------------------------------------------------------------------------
# Support probe endpoints — used by frontend probeSupportContracts()
# No auth required: these are lightweight availability checks.
# ---------------------------------------------------------------------------

@support_router.get("/health")
async def support_health():
    """Lightweight health probe for Vue SPA contract checks."""
    return {"status": "ok", "service": "autorewier"}


@support_router.get("/stats")
async def support_stats(session: AsyncSession = Depends(get_db)):
    """Aggregate stats probe for Vue SPA contract checks."""
    users_total = await session.scalar(select(func.count()).select_from(User))
    inspections_total = await session.scalar(select(func.count()).select_from(Inspection))
    return {
        "users_total": users_total or 0,
        "inspections_total": inspections_total or 0,
    }
