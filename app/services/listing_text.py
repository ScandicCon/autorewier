import re

REPAIR_KEYWORDS = (
    "менял", "меняли", "менялся", "менял", "замен", "замена", "заменен", "заменён",
    "поменял", "поменяли", "поменян", "новый", "новая", "новые", "новое",
    "свеж", "недавно", "только что", "в этом году", "на прошлой",
    "то ", "техосмотр", "обслужив", "сервис", "диагност",
    "масл", "колодк", "диск", "грм", "ремн", "цеп", "грм",
    "подвеск", "амортиз", "сайлент", "шаров", "сцеплен", "фильтр",
    "аккумулятор", "генератор", "стартер", "кондицион", "компрессор",
    "красил", "крашен", "покрас", "кузовн", "бампер", "крыло", "локер",
    "шин", "резин", "установлен", "прошёл", "прошел", "делал", "делали",
    "вложен", "вложено", "комплект", "оригинал",
)

REPAIR_CATEGORY_MAP = {
    "масл": "Двигатель",
    "грм": "Двигатель",
    "ремн": "Двигатель",
    "цеп": "Двигатель",
    "колодк": "Тормоза",
    "диск": "Тормоза",
    "подвеск": "Подвеска",
    "амортиз": "Подвеска",
    "сайлент": "Подвеска",
    "шаров": "Подвеска",
    "сцеплен": "КПП",
    "акпп": "КПП",
    "кондицион": "Климат",
    "крас": "Кузов",
    "бампер": "Кузов",
    "шин": "Колёса",
}


def extract_listing_repairs(description: str | None) -> list[str]:
    if not description:
        return []
    lines: list[str] = []
    chunks = re.split(r"[\n.;•·]+|(?<=[.!?])\s+", description)
    for chunk in chunks:
        text = chunk.strip().lstrip("-–—* ")
        if len(text) < 6:
            continue
        low = text.lower()
        if any(kw in low for kw in REPAIR_KEYWORDS):
            if text not in lines:
                lines.append(text[:300])
    if not lines and len(description) > 40:
        for line in description.splitlines():
            t = line.strip()
            if len(t) > 15:
                lines.append(t[:300])
    return lines[:15]


def repairs_to_text(repairs: list[str]) -> str:
    return "\n".join(f"• {r}" for r in repairs) if repairs else ""


def _preference_rules() -> list[tuple[str, list[str], str]]:
    return [
        (
            "Тип топлива",
            ["дизел", "бензин", "газ", "гибрид", "электро"],
            "Проверьте тип двигателя и расходники по объявлению",
        ),
        (
            "Коробка",
            ["автомат", "акпп", "механик", "мкпп", "робот", "вариатор"],
            "Сверьте КПП с объявлением на тест-драйве",
        ),
        (
            "Привод",
            ["полный", "4wd", "awd", "передний", "задний"],
            "Убедитесь в типе привода по VIN и шильдикам",
        ),
        (
            "Без ДТП",
            ["без дтп", "не бит", "без авар", "не крашен", "оригинал"],
            "Тщательно проверьте кузов толщиномером и зазоры",
        ),
        (
            "Бюджет",
            ["до ", "не дороже", "бюджет", "максимум"],
            "Сравните цену с рынком и заложите ремонт в бюджет",
        ),
        (
            "Пробег",
            ["низкий пробег", "малый пробег", "до 100", "до 150"],
            "Сверьте пробег с износом салона и историей",
        ),
        (
            "Владельцы",
            ["один владел", "1 владел", "мало владель"],
            "Запросите ПТС/ЭПТС и историю по VIN",
        ),
        (
            "Коррозия",
            ["без ржав", "не ржав", "антикор", "целые пороги"],
            "Осмотрите днище, пороги и арки",
        ),
    ]


def analyze_user_preferences(
    preferences: str | None,
    vehicle_brand: str | None = None,
    vehicle_model: str | None = None,
) -> list[str]:
    if not preferences or not preferences.strip():
        return []
    low = preferences.lower()
    notes: list[str] = []
    for title, keywords, action in _preference_rules():
        if any(kw in low for kw in keywords):
            notes.append(f"Ваше пожелание ({title}): {action}")
    if vehicle_brand and vehicle_brand.lower() not in low and vehicle_model:
        if vehicle_model.lower() in low or "только" in low or "интересует" in low:
            notes.append(
                f"Фокус на {vehicle_brand} {vehicle_model} — сравните с альтернативами по бюджету"
            )
    if not notes:
        notes.append(f"Учтены ваши пожелания: {preferences.strip()[:300]}")
    return notes[:8]


def repair_categories_claimed(repairs: list[str]) -> set[str]:
    cats: set[str] = set()
    for line in repairs:
        low = line.lower()
        for kw, cat in REPAIR_CATEGORY_MAP.items():
            if kw in low:
                cats.add(cat)
    return cats


