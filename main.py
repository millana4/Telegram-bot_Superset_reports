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
from telegram_api import router as chat_member

# Инициализация логирования
custom_logging.setup_logging()
logger = logging.getLogger(__name__)

logger.info("Настройка логирования завершена")


async def main():
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(chat_member)  # роутер ловит события, когда бота добавляют в группу
    dp.include_router(handlers.router) # роутер для обработки действий пользователей (старт, авторизация)

    # Удаляем вебхук (на всякий случай)
    await bot.delete_webhook(drop_pending_updates=True)

    me = await bot.get_me()
    logger.info("Telegram bot @%s запущен", me.username)

    accounts = [
        {
            "email": Config.IMAP_EMAIL_SR03,
            "password": Config.IMAP_PASSWORD_SR03,
            "imap": Config.IMAP_SERVER
        },
    ]

    loop = asyncio.get_running_loop()


    # Запускаем IMAP‑слушателей
    for account in accounts:
        threading.Thread(target=imap_idle_listener, args=(account, loop), daemon=True).start()

    # Запускаем Telegram‑бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())