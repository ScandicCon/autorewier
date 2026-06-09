import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from app.config import settings
from app.database import init_db
from app.bot.handlers import router


async def main() -> None:
    if not settings.telegram_bot_token:
        raise SystemExit("Укажите TELEGRAM_BOT_TOKEN в .env")

    logging.basicConfig(level=logging.INFO)
    await init_db()

    bot = Bot(
        token=settings.telegram_bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await dp.start_polling(bot)


def run_bot():
    asyncio.run(main())
