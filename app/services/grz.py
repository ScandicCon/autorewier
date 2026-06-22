"""Пробивка автомобиля по гос-номеру (ГРЗ) — аналог «Номерограм».

Гос-номер сам по себе истории не содержит: сначала по ГРЗ определяется VIN
(через Autocode, queryType="GRZ"), затем формируется обычный отчёт. Это тонкая
надстройка над VIN-проверкой.

Без ключей Autocode работает демо-режим. Результат кэшируется через слой VIN-кэша
внутри autocode.request_vin_report.
"""

import re

from app.config import settings
from app.services import autocode

# Буквы, допустимые в гос-номерах РФ (кириллица, визуально совпадают с латиницей).
_RU_LETTERS = "АВЕКМНОРСТУХ"

# Латиница → кириллица для нормализации пользовательского ввода.
_LAT_TO_CYR = str.maketrans({
    "A": "А", "B": "В", "E": "Е", "K": "К", "M": "М", "H": "Н",
    "O": "О", "P": "Р", "C": "С", "T": "Т", "Y": "У", "X": "Х",
})

# Формат: буква, 3 цифры, 2 буквы, 2–3 цифры региона. Напр. А123ВС777.
_PLATE_RE = re.compile(
    rf"^[{_RU_LETTERS}]\d{{3}}[{_RU_LETTERS}]{{2}}\d{{2,3}}$"
)


def normalize_plate(plate: str) -> str:
    """Приводит ввод к каноническому виду: верхний регистр, кириллица, без пробелов."""
    raw = (plate or "").strip().upper().replace(" ", "").replace("-", "")
    return raw.translate(_LAT_TO_CYR)


def is_valid_plate(plate: str) -> bool:
    return bool(_PLATE_RE.match(normalize_plate(plate)))


def _demo_report(plate: str) -> dict:
    return {
        "plate": plate,
        "demo": True,
        "summary": (
            f"Гос-номер {plate}: демо-режим. Подключите Autocode B2B API "
            "(queryType=GRZ) — и по номеру определится VIN, история, ограничения и залоги."
        ),
        "raw": {
            "demo": True,
            "message": "Укажите AUTOCODE_* в .env для реальной пробивки по номеру",
        },
    }


async def lookup_by_grz(plate: str) -> dict:
    """Пробивка по гос-номеру. Возвращает отчёт (демо или реальный Autocode)."""
    normalized = normalize_plate(plate)
    if not is_valid_plate(normalized):
        raise ValueError("Некорректный формат гос-номера (пример: А123ВС777)")

    if not settings.autocode_enabled:
        return _demo_report(normalized)

    report = await autocode.request_vin_report(normalized, query_type="GRZ")
    report["plate"] = normalized
    return report
