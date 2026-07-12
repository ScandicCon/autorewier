"""Учёт фактической себестоимости одной проверки.

Зачем (ПЛАН, Фаза 0.4): без реальной цифры себестоимости нельзя ни ставить цену,
ни покупать рекламу. Модуль собирает по ходу анализа расход на внешние сервисы —
токены OpenRouter (LLM) и кредиты ScrapingBee — и переводит его в рубли.

Как: аккумулятор хранится в contextvar, поэтому стоимость не нужно тащить через
сигнатуры всех функций. `start()` открывает учёт в начале обработки проверки;
`record_llm` / `record_scrapingbee` вызываются из соответствующих слоёв;
`snapshot_current()` отдаёт итог перед сохранением Inspection.

Ставки перевода в рубли настраиваются (cost_* в настройках) и зависят от модели/
тарифа, поэтому в БД кладём и сырьё (токены, кредиты), и рублёвую оценку.
contextvar копируется на задачу (запрос) — утечки между запросами нет.
"""
from __future__ import annotations

import contextlib
import contextvars

from app.config import settings

_ctx: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "cost_ctx", default=None
)


def _new() -> dict:
    return {
        "llm_calls": 0,
        "llm_prompt_tokens": 0,
        "llm_completion_tokens": 0,
        "scrapingbee_requests": 0,
        "scrapingbee_credits": 0,
    }


def start() -> dict:
    """Открывает учёт для текущей задачи (запроса). Возвращает аккумулятор."""
    acc = _new()
    _ctx.set(acc)
    return acc


@contextlib.contextmanager
def cost_context():
    """Явный контекст учёта (для тестов и точечного применения)."""
    acc = _new()
    token = _ctx.set(acc)
    try:
        yield acc
    finally:
        _ctx.reset(token)


def record_llm(prompt_tokens: int = 0, completion_tokens: int = 0) -> None:
    acc = _ctx.get()
    if acc is None:
        return
    acc["llm_calls"] += 1
    acc["llm_prompt_tokens"] += int(prompt_tokens or 0)
    acc["llm_completion_tokens"] += int(completion_tokens or 0)


def record_scrapingbee(credits: int = 0) -> None:
    acc = _ctx.get()
    if acc is None:
        return
    acc["scrapingbee_requests"] += 1
    acc["scrapingbee_credits"] += int(credits or 0)


def estimate_rub(acc: dict) -> float:
    """Оценка себестоимости в рублях по настраиваемым ставкам."""
    llm = (
        acc["llm_prompt_tokens"] / 1000 * settings.cost_llm_rub_per_1k_prompt
        + acc["llm_completion_tokens"] / 1000 * settings.cost_llm_rub_per_1k_completion
    )
    sb = acc["scrapingbee_credits"] * settings.cost_scrapingbee_rub_per_credit
    return round(llm + sb, 4)


def snapshot(acc: dict) -> dict:
    data = dict(acc)
    data["cost_rub"] = estimate_rub(acc)
    return data


def snapshot_current() -> dict:
    """Итог учёта для текущей задачи (или нулевой снимок, если учёт не открыт)."""
    acc = _ctx.get()
    return snapshot(acc if acc is not None else _new())
