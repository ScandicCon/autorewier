from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

MAIN_KB = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔍 Новая проверка")],
        [KeyboardButton(text="📋 История"), KeyboardButton(text="ℹ️ Помощь")],
    ],
    resize_keyboard=True,
)

SKIP_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="⏭ Пропустить")]],
    resize_keyboard=True,
)

CANCEL_KB = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True,
)


def yes_no_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Да"), KeyboardButton(text="Нет")],
            [KeyboardButton(text="❌ Отмена")],
        ],
        resize_keyboard=True,
    )


def inspection_actions(inspection_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Полный чеклист",
                    callback_data=f"checklist:{inspection_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="✅ После осмотра",
                    callback_data=f"post:{inspection_id}",
                )
            ],
        ]
    )


def history_item(inspection_id: int, label: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=label[:60], callback_data=f"view:{inspection_id}")]
        ]
    )
