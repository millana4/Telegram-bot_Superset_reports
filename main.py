import asyncio
import logging
import threading
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage

import handlers
import custom_logging
from config import Config
from bot import bot
from email_handler import imap_idle_listener
from database import engine
from database.sync import start_sync
from database.db_session import DbSessionMiddleware
from database.models import Base

# Инициализация логирования
custom_logging.setup_logging()
logger = logging.getLogger(__name__)

logger.info("Настройка логирования завершена")


async def main():
    # Проверка и создание таблиц (если не существуют)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("Проверка структуры БД завершена")

    dp = Dispatcher(storage=MemoryStorage())
    # Регистрирую роутер для обработки действий пользователей (старт, авторизация)
    dp.include_router(handlers.router)

    # Регистрация middleware
    dp.update.middleware(DbSessionMiddleware())

    # Удаляем вебхук (на всякий случай)
    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    logger.info("Telegram bot @%s запущен", me.username)

    accounts = [
        {
            "email": Config.IMAP_EMAIL_SR01,
            "password": Config.IMAP_PASSWORD_SR01,
            "imap": Config.IMAP_SERVER
        },
        {
            "email": Config.IMAP_EMAIL_SR02,
            "password": Config.IMAP_PASSWORD_SR02,
            "imap": Config.IMAP_SERVER
        },
    ]

    loop = asyncio.get_running_loop()

    # Запускаем синхронизацию БД
    start_sync(loop)

    # Запускаем IMAP‑слушателей
    for account in accounts:
        threading.Thread(target=imap_idle_listener, args=(account, loop), daemon=True).start()

    # Запускаем Telegram‑бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())