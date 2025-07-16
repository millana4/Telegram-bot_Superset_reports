import asyncio
import logging
import threading

from aiogram import Bot, Dispatcher
from config import Config
from email_handler import imap_idle_listener
from database.sync import start_sync

# Инициализация бота
bot = Bot(token=Config.BOT_TOKEN)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dp = Dispatcher()

async def main():
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