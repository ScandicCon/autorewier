"""Маршрут пробивки автомобиля по гос-номеру (ГРЗ).

POST /api/v1/grz/check — принимает гос-номер, определяет VIN и возвращает отчёт.
Без ключей Autocode — демо-режим (бесплатно). В реальном режиме списывается
VIN-квота (та же экономика, что у пробивки по VIN), т.к. вызов Autocode платный.
"""

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.deps import get_current_user
from app.models import User
from app.security.rate_limit import enforce_rate_limit
from app.services import grz
from app.services.analytics import track_event
from app.services.subscription import can_use_vin_report, consume_vin_report

router = APIRouter()


@router.post("/grz/check")
async def grz_check(
    request: Request,
    plate: str = Body(..., embed=True),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    await enforce_rate_limit(
        request,
        scope="grz_check",
        limit=settings.rate_limit_vin_limit,
        window_seconds=settings.rate_limit_vin_window_seconds,
        identity=str(user.id),
    )

    if not grz.is_valid_plate(plate):
        raise HTTPException(
            status_code=400,
            detail="Некорректный формат гос-номера (пример: А123ВС777)",
        )

    # В реальном режиме пробивка платная — гейтим VIN-квотой.
    if settings.autocode_enabled:
        allowed, reason = can_use_vin_report(user)
        if not allowed:
            raise HTTPException(status_code=402, detail=reason)

    await track_event("grz_lookup_requested", user_id=user.id)
    try:
        report = await grz.lookup_by_grz(plate)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if settings.autocode_enabled and not report.get("demo"):
        consume_vin_report(user)
        await session.commit()

    await track_event("grz_lookup_completed", user_id=user.id)
    return report
