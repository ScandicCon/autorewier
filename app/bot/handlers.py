import io
import logging
import re

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, Voice

from app.database import async_session
from app.schemas import AnalysisReport, InspectionCreate, InspectionPostUpdate, VehicleInput
from app.services.analysis import format_checklist_full, format_report_text
from app.services.inspections import (
    complete_post_inspection,
    create_inspection,
    get_inspection,
    get_or_create_user,
    list_user_inspections,
)
from app.bot.keyboards import (
    CANCEL_KB,
    MAIN_KB,
    SKIP_KB,
    inspection_actions,
    yes_no_kb,
)
from app.bot.states import NewCheck, PostCheck

router = Router()
URL_RE = re.compile(r"https?://\S+", re.I)
logger = logging.getLogger("autorewier.bot")


HELP_TEXT = (
    "<b>AutoRewier</b> — помощник при покупке и перепродаже авто.\n\n"
    "1. Отправьте ссылку на объявление <b>Avito</b> (или «вручную»)\n"
    "2. Дополните данные и опишите видимые дефекты\n"
    "3. Получите риски, чеклист осмотра и оценку ремонта\n"
    "4. После встречи с продавцом — «После осмотра» и итоговую рекомендацию\n\n"
    "Команды: /new — новая проверка, /history — история"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(HELP_TEXT, reply_markup=MAIN_KB)


@router.message(F.text == "ℹ️ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, reply_markup=MAIN_KB)


@router.message(F.text == "❌ Отмена")
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Отменено.", reply_markup=MAIN_KB)


@router.message(F.text == "🔍 Новая проверка")
@router.message(Command("new"))
async def new_check(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(NewCheck.url)
    await message.answer(
        "Отправьте <b>ссылку на Avito</b> (avito.ru)\n"
        "или напишите «вручную», если объявления нет.",
        reply_markup=CANCEL_KB,
    )


@router.message(NewCheck.url)
async def process_url(message: Message, state: FSMContext):
    from app.services.parsers import is_avito_url, parse_avito_url
    from app.services.listing_text import repairs_to_text

    text = (message.text or "").strip()
    if URL_RE.search(text):
        url = URL_RE.search(text).group(0)
        if "avito.ru" not in url.lower():
            await message.answer(
                "Сейчас автозагрузка только с <b>Avito</b>. "
                "Пришлите ссылку avito.ru или «вручную».",
                reply_markup=CANCEL_KB,
            )
            return
        await message.answer("⏳ Загружаю объявление с Avito…")
        parsed = await parse_avito_url(url)
        v = parsed.vehicle
        await state.update_data(
            listing_url=url,
            avito_parse_ok=parsed.parse_ok,
            brand=v.brand,
            model=v.model,
            year=v.year,
            mileage_km=v.mileage_km,
            price_rub=v.price_rub,
            description=(v.description or "").strip() or None,
            listing_repairs=repairs_to_text(parsed.listing_repairs or []),
        )
        if not parsed.parse_ok:
            next_action = ""
            if parsed.action_required == "solve_captcha":
                next_action = "\nСовет: откройте docs/AVITO.md и пройдите captcha в браузере один раз."
            elif parsed.action_required == "retry_later_or_proxy":
                next_action = "\nСовет: попробуйте позже или настройте AVITO_PROXY."
            await message.answer(
                f"⚠️ {parsed.parse_error}{next_action}\nДанные можно дополнить вручную после пожеланий."
            )
        else:
            car = f"{v.brand or ''} {v.model or ''} {v.year or ''}".strip()
            await message.answer(f"Загружено: <b>{car}</b>")
            if v.description and len(v.description) > 40:
                preview = v.description[:500] + ("…" if len(v.description) > 500 else "")
                await message.answer(
                    f"<b>Описание продавца:</b>\n{preview}",
                )
        await state.set_state(NewCheck.preferences)
        await message.answer(
            "Что для вас <b>важно</b> в этой машине?\n"
            "(бюджет, автомат, без ДТП, пробег… или «пропустить»):",
            reply_markup=SKIP_KB,
        )
        return
    if text.lower() in ("вручную", "manual", "без ссылки"):
        await state.update_data(listing_url=None)
        await state.set_state(NewCheck.brand)
        await message.answer("Введите <b>марку</b> (например, Toyota):", reply_markup=CANCEL_KB)
        return
    await message.answer("Пришлите ссылку https://www.avito.ru/… или «вручную»")


@router.message(NewCheck.preferences)
async def process_preferences(message: Message, state: FSMContext):
    t = message.text.strip()
    if t not in ("⏭ Пропустить", "пропустить", "-"):
        await state.update_data(user_preferences=t)
    await state.set_state(NewCheck.defects)
    await message.answer(
        "Опишите <b>дефекты</b> по объявлению/фото (или «пропустить»):",
        reply_markup=SKIP_KB,
    )


@router.message(NewCheck.brand)
async def process_brand(message: Message, state: FSMContext):
    await state.update_data(brand=message.text.strip())
    await state.set_state(NewCheck.model)
    await message.answer("Введите <b>модель</b>:")


@router.message(NewCheck.model)
async def process_model(message: Message, state: FSMContext):
    await state.update_data(model=message.text.strip())
    await state.set_state(NewCheck.year)
    await message.answer("Введите <b>год выпуска</b> (или «пропустить»):", reply_markup=SKIP_KB)


@router.message(NewCheck.year)
async def process_year(message: Message, state: FSMContext):
    t = message.text.strip()
    if t != "⏭ Пропустить":
        try:
            await state.update_data(year=int(t))
        except ValueError:
            await message.answer("Введите число, например 2018")
            return
    await state.set_state(NewCheck.mileage)
    await message.answer("Введите <b>пробег</b> в км (или пропустить):", reply_markup=SKIP_KB)


@router.message(NewCheck.mileage)
async def process_mileage(message: Message, state: FSMContext):
    t = message.text.strip().replace(" ", "")
    if t != "⏭Пропустить" and t != "⏭ Пропустить":
        digits = re.sub(r"\D", "", t)
        if digits:
            await state.update_data(mileage_km=int(digits))
    await state.set_state(NewCheck.price)
    await message.answer("Введите <b>цену</b> в ₽ (или пропустить):", reply_markup=SKIP_KB)


@router.message(NewCheck.price)
async def process_price(message: Message, state: FSMContext):
    t = message.text.strip()
    if t != "⏭ Пропустить":
        digits = re.sub(r"\D", "", t)
        if digits:
            await state.update_data(price_rub=int(digits))
    await state.set_state(NewCheck.preferences)
    await message.answer(
        "Что для вас <b>важно</b> в машине? (или «пропустить»):",
        reply_markup=SKIP_KB,
    )


@router.message(NewCheck.defects)
async def process_defects(message: Message, state: FSMContext):
    t = message.text.strip()
    if t not in ("⏭ Пропустить", "пропустить", "-"):
        await state.update_data(pre_defects=t)
    await state.set_state(NewCheck.reseller)
    await message.answer(
        "Вы перекупщик? Нужна оценка маржи?",
        reply_markup=yes_no_kb(),
    )


@router.message(NewCheck.reseller)
async def process_reseller(message: Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await cancel(message, state)
        return
    is_reseller = message.text.lower().startswith("д")
    await state.update_data(is_reseller=is_reseller)
    if is_reseller:
        await state.set_state(NewCheck.target_price)
        await message.answer(
            "Целевая цена <b>перепродажи</b> в ₽ (или пропустить — посчитаем +12%):",
            reply_markup=SKIP_KB,
        )
    else:
        await _finish_new_check(message, state)


@router.message(NewCheck.target_price)
async def process_target(message: Message, state: FSMContext):
    t = message.text.strip()
    if t != "⏭ Пропустить":
        digits = re.sub(r"\D", "", t)
        if digits:
            await state.update_data(target_resale_price=int(digits))
    await _finish_new_check(message, state)


async def _finish_new_check(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    vehicle = VehicleInput(
        brand=data.get("brand"),
        model=data.get("model"),
        year=data.get("year"),
        mileage_km=data.get("mileage_km"),
        price_rub=data.get("price_rub"),
        description=data.get("description"),
    )
    body = InspectionCreate(
        listing_url=data.get("listing_url"),
        vehicle=vehicle if any(vehicle.model_dump().values()) else None,
        user_preferences=data.get("user_preferences"),
        listing_repairs=data.get("listing_repairs"),
        pre_defects=data.get("pre_defects"),
        is_reseller=data.get("is_reseller", False),
        target_resale_price=data.get("target_resale_price"),
        require_avito_parse=bool(
            data.get("listing_url") and data.get("avito_parse_ok")
        ),
    )

    await message.answer("⏳ Анализирую объявление…", reply_markup=MAIN_KB)

    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id)
        try:
            ins = await create_inspection(session, user, body)
        except PermissionError as e:
            await message.answer(str(e), reply_markup=MAIN_KB)
            return
        except ValueError as e:
            await message.answer(str(e), reply_markup=MAIN_KB)
            return

    report = AnalysisReport(**ins.pre_report)
    text = format_report_text(report, title=f"Проверка #{ins.id}")
    await message.answer(
        text,
        reply_markup=inspection_actions(ins.id),
    )
    car = f"{ins.brand or ''} {ins.model or ''}".strip() or "Автомобиль"
    await message.answer(
        f"Сохранено: <b>{car}</b>. Перед осмотром откройте полный чеклист.",
        reply_markup=MAIN_KB,
    )


@router.callback_query(F.data.startswith("checklist:"))
async def cb_checklist(query: CallbackQuery):
    iid = int(query.data.split(":")[1])
    async with async_session() as session:
        user = await get_or_create_user(session, query.from_user.id)
        ins = await get_inspection(session, iid, user.id)
    if not ins or not ins.pre_report:
        await query.answer("Не найдено", show_alert=True)
        return
    report = AnalysisReport(**(ins.post_report or ins.pre_report))
    await query.message.answer(format_checklist_full(report))
    await query.answer()


@router.callback_query(F.data.startswith("post:"))
async def cb_post_start(query: CallbackQuery, state: FSMContext):
    iid = int(query.data.split(":")[1])
    await state.set_state(PostCheck.defects)
    await state.update_data(inspection_id=iid)
    await query.message.answer(
        f"Проверка #{iid}. Опишите <b>все дефекты</b>, найденные при осмотре:",
        reply_markup=CANCEL_KB,
    )
    await query.answer()


@router.message(PostCheck.defects)
async def post_defects(message: Message, state: FSMContext):
    await state.update_data(post_defects=message.text.strip())
    await state.set_state(PostCheck.notes)
    await message.answer(
        "Дополнительные <b>комментарии</b> (или «пропустить»):",
        reply_markup=SKIP_KB,
    )


@router.message(PostCheck.notes)
async def post_notes(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    notes = None if message.text.strip() == "⏭ Пропустить" else message.text.strip()
    iid = data["inspection_id"]

    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id)
        ins = await complete_post_inspection(
            session,
            iid,
            user.id,
            InspectionPostUpdate(
                post_defects=data["post_defects"],
                post_notes=notes,
            ),
        )

    if not ins:
        await message.answer("Проверка не найдена.", reply_markup=MAIN_KB)
        return

    report = AnalysisReport(**ins.post_report)
    text = format_report_text(report, title=f"Итог #{ins.id}")
    await message.answer(text, reply_markup=MAIN_KB)


@router.message(F.text == "📋 История")
@router.message(Command("history"))
async def history(message: Message):
    async with async_session() as session:
        user = await get_or_create_user(session, message.from_user.id)
        items = await list_user_inspections(session, user.id, limit=10)

    if not items:
        await message.answer("История пуста. Начните с «Новая проверка».", reply_markup=MAIN_KB)
        return

    lines = ["<b>История проверок</b>\n"]
    for ins in items:
        v = ins.verdict.value if ins.verdict else "—"
        car = f"{ins.brand or '?'} {ins.model or ''} {ins.year or ''}".strip()
        lines.append(f"#{ins.id} {car} — {v}")
    await message.answer("\n".join(lines), reply_markup=MAIN_KB)


@router.callback_query(F.data.startswith("view:"))
async def cb_view(query: CallbackQuery):
    iid = int(query.data.split(":")[1])
    async with async_session() as session:
        user = await get_or_create_user(session, query.from_user.id)
        ins = await get_inspection(session, iid, user.id)
    if not ins:
        await query.answer("Не найдено", show_alert=True)
        return
    data = ins.post_report or ins.pre_report
    report = AnalysisReport(**data)
    await query.message.answer(format_report_text(report, title=f"#{ins.id}"))
    await query.answer()


# ---------------------------------------------------------------------------
# Голосовой ввод
# ---------------------------------------------------------------------------

@router.message(F.voice)
async def handle_voice(message: Message, state: FSMContext):
    """Принимает голосовое сообщение, транскрибирует и обрабатывает как текст."""
    from app.services.transcription import transcribe_voice
    from app.config import settings

    if not settings.openrouter_api_key.strip():
        await message.answer(
            "Голосовой ввод недоступен: не настроен OPENROUTER_API_KEY.",
            reply_markup=MAIN_KB,
        )
        return

    voice: Voice = message.voice
    await message.answer("🎙 Распознаю голосовое сообщение…")

    try:
        # Скачиваем файл через Telegram Bot API
        bot = message.bot
        file_info = await bot.get_file(voice.file_id)
        file_bytes_io = io.BytesIO()
        await bot.download_file(file_info.file_path, file_bytes_io)
        audio_bytes = file_bytes_io.getvalue()

        transcript = await transcribe_voice(audio_bytes, filename="voice.ogg")
    except RuntimeError as exc:
        await message.answer(f"Не удалось распознать голос: {exc}", reply_markup=MAIN_KB)
        return
    except Exception as exc:
        logger.exception("voice_transcription_failed", extra={"error": str(exc)})
        await message.answer(
            "Произошла ошибка при распознавании голоса. Попробуйте ещё раз.",
            reply_markup=MAIN_KB,
        )
        return

    if not transcript:
        await message.answer(
            "Не удалось распознать речь. Попробуйте говорить чётче или введите текст.",
            reply_markup=MAIN_KB,
        )
        return

    await message.answer(f"Распознано: <i>{transcript}</i>")

    # Имитируем текстовое сообщение — обрабатываем транскрипт в текущем состоянии FSM
    current_state = await state.get_state()

    # Создаём псевдо-сообщение с текстом транскрипта
    # Используем оригинальный message и подменяем .text через monkey-patch объекта
    # (aiogram Message — frozen dataclass, поэтому создаём обёртку)
    class _FakeMessage:
        """Минимальная обёртка для передачи транскрипта в обработчики состояний."""
        def __init__(self, original: Message, text: str):
            self._orig = original
            self.text = text
            self.from_user = original.from_user
            self.bot = original.bot

        async def answer(self, *args, **kwargs):
            return await self._orig.answer(*args, **kwargs)

    fake_msg = _FakeMessage(message, transcript)

    # Роутим в обработчик состояния
    state_handlers = {
        NewCheck.url: process_url,
        NewCheck.preferences: process_preferences,
        NewCheck.defects: process_defects,
        NewCheck.brand: process_brand,
        NewCheck.model: process_model,
        PostCheck.defects: post_defects,
        PostCheck.notes: post_notes,
    }

    handler = None
    for state_key, fn in state_handlers.items():
        if current_state == state_key.state:
            handler = fn
            break

    if handler:
        await handler(fake_msg, state)  # type: ignore[arg-type]
    else:
        # Вне FSM — обрабатываем как обычный текст (URL или «вручную»)
        await process_url(fake_msg, state)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Мониторинг: отправка уведомлений через бот
# ---------------------------------------------------------------------------

async def send_monitoring_notification(
    telegram_user_id: int,
    listing,
    event,
) -> None:
    """Отправляет пользователю уведомление об изменении мониторимого объявления.

    Args:
        telegram_user_id: ID пользователя в Telegram (из User.telegram_id).
        listing: MonitoredListing — объявление с изменением.
        event: ListingChangeEvent — событие изменения.
    """
    from app.config import settings
    from aiogram import Bot
    from aiogram.enums import ParseMode
    from app.models import ChangeType

    if not settings.telegram_bot_token.strip():
        logger.warning("monitoring_notification_no_bot_token")
        return

    # Получаем telegram_id пользователя через БД
    from app.database import async_session as db_session
    from app.models import User
    from sqlalchemy import select

    async with db_session() as session:
        result = await session.execute(
            select(User.telegram_id).where(User.id == listing.user_id)
        )
        row = result.one_or_none()

    if not row or not row[0]:
        logger.info(
            "monitoring_notification_no_telegram_id",
            extra={"user_id": listing.user_id},
        )
        return

    tg_id = row[0]

    change_type = event.change_type
    if change_type == ChangeType.PRICE_DROP:
        icon = "📉"
        action = f"Цена снижена: {event.old_value} → {event.new_value} ₽"
    elif change_type == ChangeType.PRICE_RISE:
        icon = "📈"
        action = f"Цена повышена: {event.old_value} → {event.new_value} ₽"
    elif change_type == ChangeType.SOLD:
        icon = "✅"
        action = "Объявление помечено как продано"
    else:
        icon = "🗑"
        action = "Объявление снято с продажи"

    url_preview = listing.url[:80] + "…" if len(listing.url) > 80 else listing.url
    text = (
        f"{icon} <b>Изменение объявления</b>\n\n"
        f"{action}\n"
        f"URL: <a href=\"{listing.url}\">{url_preview}</a>"
    )

    try:
        bot = Bot(token=settings.telegram_bot_token, parse_mode=ParseMode.HTML)
        await bot.send_message(tg_id, text, disable_web_page_preview=True)
        await bot.session.close()
    except Exception as exc:
        logger.warning(
            "monitoring_notification_send_failed",
            extra={"tg_id": tg_id, "error": str(exc)},
        )
