import asyncio
import logging
import threading

from aiogram import Bot, Dispatcher
from config import Config
from email_handler import imap_idle_listener

# Инициализация бота
bot = Bot(token=Config.BOT_TOKEN)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dp = Dispatcher()
dp.include_router(chat_member) # роутер ловит события, когда бота добавляют в группу

async def main():
    me = await bot.get_me()
    logger.info("Telegram bot @%s запущен", me.username)

    await bot.delete_webhook(drop_pending_updates=True) # пропускает апдейты, которые накопились пока бот был офлайн

    # Заполняем аккаунты из Config
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

    # Запускаем IMAP‑слушателей в отдельных потоках
    for account in accounts:
        threading.Thread(target=imap_idle_listener, args=(account, loop), daemon=True).start()

    # Запускаем Telegram‑бота
    await dp.start_polling(bot, allowed_updates=["chat_member", "my_chat_member"])

if __name__ == "__main__":
    asyncio.run(main())