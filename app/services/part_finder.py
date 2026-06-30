"""Поиск б/у детали по фотографии.

Пользователь загружает фото детали (фара, бампер, зеркало, диск, фонарь и т.д.).
Vision-LLM определяет, что это за деталь и на какую технику она похожа, строит
поисковый запрос и ищет похожие б/у объявления на Авито (со ссылками).

Архитектура осознанно собрана из готовых кусков проекта:
- vision через тот же OpenRouter-клиент, что и `image_analysis.py`;
- поиск объявлений через уже существующий `parts_prices.search_avito_parts`.

ВАЖНО (продуктовое ограничение, сообщается пользователю явно):
это поиск ПОХОЖИХ деталей по фото, а НЕ гарантия совместимости. Точную
совместимость и OEM-номер по одной фотографии определить нельзя.

Мягкая деградация (как и везде в проекте):
- есть ключ OpenRouter  → реальный vision + реальный поиск по Авито;
- нет ключа, но разрешён mock → демо-результат (без сети), помечен demo=True;
- нет ключа и mock запрещён (прод) → пустой результат с понятным note, без падения.
"""
from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field

from app.config import settings
from app.schemas import AvitoPartOffer
from app.services.parts_prices import build_avito_search_url, search_avito_parts

logger = logging.getLogger(__name__)

MAX_OFFERS = 5

DISCLAIMER = (
    "Это похожие детали по фото, а не гарантия совместимости. "
    "Точную применимость и OEM-номер по одной фотографии определить нельзя — "
    "перед покупкой сверьте деталь по каталожному номеру и году/модели вашей техники."
)

VISION_PART_PROMPT = (
    "Ты эксперт по автозапчастям и разборкам в РФ. На фото — деталь техники "
    "(автомобиль, мото, спецтехника). Определи, ЧТО это за деталь, и собери "
    "поисковый запрос для б/у объявлений на Авито. "
    "Не выдумывай точную совместимость, если её не видно — лучше укажи общий тип детали. "
    "Ответ СТРОГО одним JSON-объектом без пояснений: "
    '{"part_name":"короткое название детали по-русски",'
    '"category":"группа (Оптика|Кузов|Подвеска|Двигатель|Салон|Электрика|Колёса|Прочее)",'
    '"vehicle_hint":"марка/модель если уверенно видно, иначе null",'
    '"search_query":"строка для поиска на Авито (деталь + марка/модель если есть)",'
    '"keywords":["ключевые","слова"],'
    '"confidence":0-100,'
    '"notes":"что мешает точности (если есть), иначе null"}'
)


class PartIdentification(BaseModel):
    """Что нейросеть «увидела» на фото детали."""

    part_name: str
    category: str | None = None
    vehicle_hint: str | None = None
    search_query: str
    keywords: list[str] = Field(default_factory=list)
    confidence: int = Field(default=50, ge=0, le=100)
    notes: str | None = None


class PartFinderResult(BaseModel):
    """Итог поиска детали по фото."""

    identification: PartIdentification
    offers: list[AvitoPartOffer] = Field(default_factory=list)
    search_url: str
    disclaimer: str = DISCLAIMER
    demo: bool = False


def _clean_json(raw: str) -> str:
    raw = (raw or "{}").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return raw or "{}"


def _coerce_identification(data: dict) -> PartIdentification:
    """Аккуратно собрать PartIdentification из сырого ответа модели."""
    part_name = str(data.get("part_name") or "").strip() or "запчасть"

    raw_query = str(data.get("search_query") or "").strip()
    vehicle = data.get("vehicle_hint")
    vehicle = str(vehicle).strip() if vehicle else None
    if vehicle and vehicle.lower() in {"null", "none", "-"}:
        vehicle = None

    query = raw_query or " ".join(p for p in [part_name, vehicle] if p)

    keywords = data.get("keywords") or []
    if not isinstance(keywords, list):
        keywords = []
    keywords = [str(k).strip() for k in keywords if str(k).strip()][:8]

    try:
        confidence = int(data.get("confidence", 50))
    except (TypeError, ValueError):
        confidence = 50
    confidence = max(0, min(100, confidence))

    notes = data.get("notes")
    notes = str(notes).strip() if notes else None
    if notes and notes.lower() in {"null", "none"}:
        notes = None

    category = data.get("category")
    category = str(category).strip() if category else None

    return PartIdentification(
        part_name=part_name,
        category=category,
        vehicle_hint=vehicle,
        search_query=query,
        keywords=keywords,
        confidence=confidence,
        notes=notes,
    )


async def _identify_part(photo_data_url: str, hint: str | None = None) -> PartIdentification:
    """Распознать деталь на фото через vision-LLM (OpenRouter)."""
    from app.services.llm import _openrouter_client

    user_text = VISION_PART_PROMPT
    if hint and hint.strip():
        user_text += f"\nПодсказка от пользователя (учти): {hint.strip()}"

    client = _openrouter_client()
    response = await client.chat.completions.create(
        model=settings.openrouter_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": photo_data_url}},
                    {"type": "text", "text": user_text},
                ],
            }
        ],
        temperature=0.2,
        max_tokens=300,
    )
    raw = _clean_json(response.choices[0].message.content or "{}")
    data = json.loads(raw)
    identification = _coerce_identification(data)

    # Если пользователь дал подсказку, а модель её не учла в запросе — добавим.
    if hint and hint.strip() and hint.strip().lower() not in identification.search_query.lower():
        identification.search_query = f"{identification.search_query} {hint.strip()}".strip()
    return identification


def _mock_result(hint: str | None = None) -> PartFinderResult:
    """Демо-результат без сети (нет ключа OpenRouter, но mock разрешён)."""
    query = "фара передняя" + (f" {hint.strip()}" if hint and hint.strip() else "")
    identification = PartIdentification(
        part_name="Фара передняя",
        category="Оптика",
        vehicle_hint=hint.strip() if hint and hint.strip() else None,
        search_query=query,
        keywords=["фара", "передняя", "оптика"],
        confidence=40,
        notes="Демо-режим: ИИ-распознавание выключено (нет ключа OpenRouter).",
    )
    offers = [
        AvitoPartOffer(
            title="Фара передняя левая (демо-пример)",
            price_rub=4500,
            url=build_avito_search_url(query),
        ),
        AvitoPartOffer(
            title="Фара передняя правая (демо-пример)",
            price_rub=4800,
            url=build_avito_search_url(query),
        ),
    ]
    return PartFinderResult(
        identification=identification,
        offers=offers,
        search_url=build_avito_search_url(query),
        demo=True,
    )


async def find_parts_by_photo(
    photo_data_url: str,
    hint: str | None = None,
    max_offers: int = MAX_OFFERS,
) -> PartFinderResult:
    """Главная точка входа: фото детали → распознавание → похожие объявления на Авито."""
    # Нет ИИ-ключа.
    if not settings.llm_enabled:
        if settings.can_use_mock_services:
            return _mock_result(hint)
        # Прод без ключа — не падаем, отдаём понятный пустой результат.
        identification = PartIdentification(
            part_name="не распознано",
            search_query=(hint or "").strip() or "запчасть",
            confidence=0,
            notes="Распознавание по фото временно недоступно — попробуйте позже.",
        )
        return PartFinderResult(
            identification=identification,
            offers=[],
            search_url=build_avito_search_url(identification.search_query),
        )

    # Боевой путь: vision + поиск по Авито.
    try:
        identification = await _identify_part(photo_data_url, hint=hint)
    except Exception as exc:  # noqa: BLE001 — мягкая деградация
        logger.warning("part vision identification failed: %s", exc)
        fallback_query = (hint or "").strip() or "запчасть"
        identification = PartIdentification(
            part_name="не распознано",
            search_query=fallback_query,
            confidence=0,
            notes="Не удалось распознать деталь по фото — уточните запрос вручную.",
        )

    search_url = build_avito_search_url(identification.search_query)

    offers: list[AvitoPartOffer] = []
    if identification.confidence > 0:
        try:
            offers = await search_avito_parts(identification.search_query)
            offers = offers[:max_offers]
        except Exception as exc:  # noqa: BLE001
            logger.warning("avito parts search failed: %s", exc)
            offers = []

    return PartFinderResult(
        identification=identification,
        offers=offers,
        search_url=search_url,
    )
