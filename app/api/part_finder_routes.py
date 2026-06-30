"""Маршрут поиска б/у детали по фотографии.

POST /api/v1/parts/find-by-photo — пользователь загружает одно фото детали
(плюс необязательную текстовую подсказку), сервис распознаёт деталь нейросетью
и возвращает похожие объявления на Авито со ссылками.

Фото на диск не сохраняется: кодируется в base64 data-URL и уходит во vision.
Без ключа OpenRouter работает демо-режим (как и остальные ИИ-фичи проекта).
"""

import base64

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.config import settings
from app.deps import get_current_user
from app.models import User
from app.security.rate_limit import enforce_rate_limit
from app.services.analytics import track_event
from app.services.part_finder import PartFinderResult, find_parts_by_photo

router = APIRouter()

MAX_PHOTO_BYTES = 8 * 1024 * 1024  # 8 МБ
MAX_HINT_LEN = 120


@router.post("/parts/find-by-photo", response_model=PartFinderResult)
async def find_part_by_photo(
    request: Request,
    file: UploadFile = File(...),
    hint: str | None = Form(None),
    user: User = Depends(get_current_user),
):
    """Поиск похожей б/у детали по фотографии."""
    await enforce_rate_limit(
        request,
        scope="parts_find_by_photo",
        limit=settings.rate_limit_vin_limit,
        window_seconds=settings.rate_limit_vin_window_seconds,
        identity=str(user.id),
    )

    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"Файл «{file.filename or 'без имени'}» — не изображение",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Пустой файл")
    if len(data) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Файл больше 8 МБ")

    if hint is not None:
        hint = hint.strip()[:MAX_HINT_LEN] or None

    b64 = base64.b64encode(data).decode()
    data_url = f"data:{content_type};base64,{b64}"

    await track_event("part_search_by_photo_requested", user_id=user.id)

    result = await find_parts_by_photo(data_url, hint=hint)

    await track_event(
        "part_search_by_photo_completed",
        user_id=user.id,
        props={
            "offers": len(result.offers),
            "confidence": result.identification.confidence,
            "demo": result.demo,
        },
    )
    return result
