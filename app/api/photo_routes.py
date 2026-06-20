"""Нейросетевой анализ загруженных фото авто.

Отдельный роутер: пользователь загружает фото кузова, они кодируются в base64 и
передаются во vision-движок (`analyze_photo_urls`), который возвращает находки
по повреждениям (зона, дефект, уверенность). Фото на диск не сохраняются.
"""

import base64

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.config import settings
from app.deps import get_current_user
from app.models import User
from app.schemas import ImageFinding, PhotoMetadataInput
from app.security.rate_limit import enforce_rate_limit
from app.services.analytics import track_event
from app.services.image_analysis import analyze_photo_urls

router = APIRouter()

MAX_PHOTOS_PER_REQUEST = 5
MAX_PHOTO_BYTES = 8 * 1024 * 1024  # 8 МБ на файл


@router.post("/photos/analyze", response_model=list[ImageFinding])
async def analyze_uploaded_photos(
    request: Request,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
):
    """Анализ загруженных фото авто нейросетью (повреждения по зонам кузова)."""
    await enforce_rate_limit(
        request,
        scope="photos_analyze",
        limit=settings.rate_limit_vin_limit,
        window_seconds=settings.rate_limit_vin_window_seconds,
        identity=str(user.id),
    )
    if not files:
        raise HTTPException(status_code=400, detail="Не приложено ни одного фото")
    if len(files) > MAX_PHOTOS_PER_REQUEST:
        raise HTTPException(
            status_code=400,
            detail=f"Максимум {MAX_PHOTOS_PER_REQUEST} фото за один запрос",
        )

    photos: list[PhotoMetadataInput] = []
    for f in files:
        content_type = (f.content_type or "").lower()
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"Файл «{f.filename or 'без имени'}» — не изображение",
            )
        data = await f.read()
        if not data:
            continue
        if len(data) > MAX_PHOTO_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"Файл «{f.filename or 'без имени'}» больше 8 МБ",
            )
        b64 = base64.b64encode(data).decode()
        data_url = f"data:{content_type};base64,{b64}"
        photos.append(PhotoMetadataInput(photo_url=data_url, note=f.filename))

    if not photos:
        raise HTTPException(status_code=400, detail="Пустые файлы")

    findings = await analyze_photo_urls(photos)
    await track_event(
        "photo_analysis_completed",
        user_id=user.id,
        props={"count": len(photos)},
    )
    return findings
