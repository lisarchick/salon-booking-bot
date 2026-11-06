import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import BOT_TOKEN
import database as db
from middleware import RegistrationMiddleware
from scheduler import setup_scheduler

from handlers import registration, masters, booking, profile, support, admin, banning

logging.basicConfig(level=logging.INFO)


async def main():
    db.init_db()

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())

    dp.message.middleware(RegistrationMiddleware())
    dp.callback_query.middleware(RegistrationMiddleware())

    # order matters: registration first (handles /start before user exists)
    dp.include_router(registration.router)
    dp.include_router(admin.router)
    dp.include_router(banning.router)
    dp.include_router(masters.router)
    dp.include_router(booking.router)
    dp.include_router(profile.router)
    dp.include_router(support.router)

    setup_scheduler(bot)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
