"""Торговый аргументатор: генерирует фразы для торга на основе рисков и цены авто."""
from __future__ import annotations

import json
import logging

from app.config import settings
from app.schemas import AnalysisReport, VehicleInput

logger = logging.getLogger(__name__)


async def generate_negotiation_tips(
    report: AnalysisReport,
    vehicle: VehicleInput,
) -> list[str]:
    """
    Вызывает LLM и возвращает 3-5 конкретных фраз для торга с продавцом.
    При отсутствии ключа или ошибке возвращает [].
    """
    if not settings.llm_enabled:
        return []

    try:
        from app.services.llm import _openrouter_client

        # Собираем только высокие и средние риски с оценкой стоимости
        risks_summary = []
        for r in report.risks:
            if r.severity in ("high", "medium"):
                cost_hint = ""
                if r.estimated_cost_min is not None and r.estimated_cost_max is not None:
                    cost_hint = f" (ремонт ~{r.estimated_cost_min:,}–{r.estimated_cost_max:,} ₽)".replace(",", " ")
                risks_summary.append(f"{r.title}: {r.description}{cost_hint}")

        payload = {
            "brand": vehicle.brand or "не указано",
            "model": vehicle.model or "не указано",
            "year": vehicle.year,
            "price_rub": vehicle.price_rub,
            "repair_total_min": report.repair_total_min,
            "repair_total_max": report.repair_total_max,
            "risks": risks_summary[:8],
        }

        system_prompt = (
            "Ты эксперт по переговорам при покупке подержанного авто в РФ. "
            "По данным анализа авто составь 3-5 конкретных фраз для торга с продавцом. "
            "Каждая фраза — прямая речь покупателя, опирающаяся на конкретный риск или дефект. "
            "Фразы должны быть вежливыми, аргументированными и указывать конкретную сумму скидки там, где это уместно. "
            "Ответ ТОЛЬКО в формате JSON-массива строк: "
            '[\"Скажите продавцу: \'...\'\", ...]'
        )

        client = _openrouter_client()
        response = await client.chat.completions.create(
            model=settings.openrouter_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
            temperature=0.4,
            max_tokens=600,
        )

        raw = (response.choices[0].message.content or "[]").strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        tips = json.loads(raw)
        if isinstance(tips, list):
            return [str(t) for t in tips if t][:5]
        return []

    except Exception as exc:
        logger.warning("generate_negotiation_tips failed: %s", exc)
        return []
