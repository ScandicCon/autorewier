"""Vision-анализ фотографий автомобиля через multimodal LLM (OpenRouter)."""
from __future__ import annotations

import asyncio
import json
import logging
from urllib.parse import urlparse

from app.config import settings
from app.schemas import ConfidenceEnum, ImageFinding, PhotoMetadataInput

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------- #
# Keyword-based fallback (когда LLM недоступен)
# --------------------------------------------------------------------------- #

_ZONE_HINTS = {
    "bumper": "Кузов",
    "fender": "Кузов",
    "hood": "Кузов",
    "door": "Кузов",
    "rust": "Кузов",
    "engine": "Двигатель",
    "leak": "Двигатель",
    "oil": "Двигатель",
    "transmission": "КПП",
    "gearbox": "КПП",
    "wheel": "Подвеска",
    "suspension": "Подвеска",
    "brake": "Тормоза",
}

_ISSUE_HINTS = {
    "scratch": ("Следы повреждения ЛКП", ConfidenceEnum.medium),
    "dent": ("Возможна вмятина или след кузовного ремонта", ConfidenceEnum.medium),
    "rust": ("Признаки коррозии", ConfidenceEnum.high),
    "leak": ("Возможны следы течи технических жидкостей", ConfidenceEnum.high),
    "crack": ("Возможна трещина элемента", ConfidenceEnum.high),
    "wear": ("Признаки износа", ConfidenceEnum.medium),
}

_VALID_ZONES = {"Кузов", "Двигатель", "Подвеска", "Тормоза", "Салон", "Другое"}
_VALID_CONFIDENCES = {"low", "medium", "high"}

VISION_PROMPT = (
    "Ты эксперт осмотра авто РФ. Опиши что видишь на фото: "
    "дефекты кузова, следы ДТП, перекрас, коррозию, подтёки. "
    'Ответ ТОЛЬКО JSON: {"zone": "Кузов|Двигатель|Подвеска|Тормоза|Салон|Другое", '
    '"issue": "краткое описание", "confidence": "low|medium|high"}'
)


def _lower_chunks(photo: PhotoMetadataInput) -> str:
    raw = " ".join(
        part.strip()
        for part in [photo.photo_url or "", photo.note or "", photo.zone or ""]
        if part
    )
    return raw.lower()


def _zone_from_text(text: str, fallback: str | None) -> str | None:
    if fallback and fallback.strip():
        return fallback.strip()
    for key, zone in _ZONE_HINTS.items():
        if key in text:
            return zone
    return None


def _issue_from_text(text: str) -> tuple[str, ConfidenceEnum]:
    for key, value in _ISSUE_HINTS.items():
        if key in text:
            return value
    return ("Требуется визуальная проверка фото на осмотре", ConfidenceEnum.low)


def _safe_host(url: str | None) -> str:
    if not url:
        return "unknown"
    try:
        return urlparse(url).netloc.lower() or "unknown"
    except Exception:
        return "unknown"


def _keyword_finding(photo: PhotoMetadataInput) -> ImageFinding:
    """Fallback: анализ по URL/подписи без LLM."""
    text = _lower_chunks(photo)
    zone = _zone_from_text(text, photo.zone)
    issue, confidence = _issue_from_text(text)
    return ImageFinding(
        source=f"photo_url:{_safe_host(photo.photo_url)}",
        zone=zone,
        issue=issue,
        confidence=confidence,
        rationale="Оценка по URL/подписи фото. Это предварительный сигнал, подтвердите на живом осмотре.",
        action="Сверьте дефект на месте и запросите диагностику при покупке.",
    )


async def _analyze_photo_with_llm(photo: PhotoMetadataInput) -> ImageFinding:
    """
    Отправляет одно фото в multimodal LLM.
    При любой ошибке — возвращает keyword fallback.
    """
    if not photo.photo_url:
        return _keyword_finding(photo)

    try:
        from app.services.llm import _openrouter_client

        client = _openrouter_client()
        response = await client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": photo.photo_url},
                        },
                        {
                            "type": "text",
                            "text": VISION_PROMPT,
                        },
                    ],
                }
            ],
            temperature=0.2,
            max_tokens=200,
        )

        raw = (response.choices[0].message.content or "{}").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        data = json.loads(raw)

        zone = data.get("zone", "Другое")
        if zone not in _VALID_ZONES:
            zone = "Другое"

        issue = str(data.get("issue", "")).strip() or "Нет явных дефектов на фото"

        confidence_raw = str(data.get("confidence", "medium")).lower()
        if confidence_raw not in _VALID_CONFIDENCES:
            confidence_raw = "medium"
        confidence = ConfidenceEnum(confidence_raw)

        return ImageFinding(
            source=f"vision:{_safe_host(photo.photo_url)}",
            zone=zone,
            issue=issue,
            confidence=confidence,
            rationale="Vision-анализ фото через LLM. Подтвердите находки на живом осмотре.",
            action="Проверьте указанный дефект при личном осмотре автомобиля.",
        )

    except Exception as exc:
        logger.warning("vision analysis failed for %s: %s", photo.photo_url, exc)
        return _keyword_finding(photo)


async def analyze_photo_urls(photos: list[PhotoMetadataInput]) -> list[ImageFinding]:
    """
    Анализирует список фотографий.
    Если LLM включён — параллельные vision-запросы (до 5 фото).
    Иначе — keyword fallback для всех фото.
    """
    if not photos:
        return []

    # Берём до 5 фото с непустым photo_url для vision; остальные — keyword fallback
    vision_photos = [p for p in photos[:20] if p.photo_url][:5]
    keyword_photos = [p for p in photos[:20] if not p.photo_url]

    findings: list[ImageFinding] = []

    if settings.llm_enabled and vision_photos:
        # Параллельный vision-анализ
        tasks = [_analyze_photo_with_llm(p) for p in vision_photos]
        vision_results = await asyncio.gather(*tasks, return_exceptions=True)
        for photo, result in zip(vision_photos, vision_results):
            if isinstance(result, ImageFinding):
                findings.append(result)
            else:
                # gather вернул исключение — fallback
                findings.append(_keyword_finding(photo))
    else:
        # LLM выключен — keyword fallback для всех vision-фото
        for photo in vision_photos:
            findings.append(_keyword_finding(photo))

    # Keyword fallback для фото без URL
    for photo in keyword_photos:
        findings.append(_keyword_finding(photo))

    return findings
