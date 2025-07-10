import aiocron
import asyncio
import logging
from database.seatable_client import fetch_tables
from database.crud import insert_new_users
from config import Config


logger = logging.getLogger(__name__)

async def daily_sync():
    """Планировщик ежедневной синхронизации. Ищет новых пользователей в Seatable и добавляет их в Postgres"""
    logger.info("Старт синхронизации с Seatable.")
    rows = await fetch_tables(Config.SEATABLE_USERS_TABLE_ID)  # Получает всех пользователей Получает имейлы пользователей fetch_tables(Config.SEATABLE_EMAIL_TABLE_ID)
    await insert_new_users(rows) # Добавляет в БД бота Postgres новых пользователей
    logger.info("Синхронизация с SeaTable завершена.")

# Создаем cron с расписанием синхронизации. Но не запускаем, чтобы не открыть второй Event-loop
cron = aiocron.crontab(
    f"{Config.SYNC_TIME_UTC.split(':')[1]} " # минуты
    f"{Config.SYNC_TIME_UTC.split(':')[0]} "       # часы
    "* * *",
    func=lambda: asyncio.create_task(daily_sync()),
    start=False
)

def start_sync(loop: asyncio.AbstractEventLoop):
    """Запускает cron в существующем Event-loop"""
    cron.loop = loop
    cron.start()

    asyncio.create_task(daily_sync())  # старт синхронизации при запуске бота без привязки ко времени

