import asyncio
import logging
from datetime import datetime, time, timedelta
from database.crud import insert_new_users
from config import Config


logger = logging.getLogger(__name__)


class Scheduler:
    def __init__(self):
        self._task = None

    async def sync(self, startup=False):
        """Основная функция синхронизации"""
        try:
            if startup:
                logger.info("Старт синхронизации БД с Seatable при запуске бота")
            else:
                logger.info("Запуск ежедневной синхронизации БД с Seatable")

            await insert_new_users()

            if startup:
                logger.info("Синхронизация БД с Seatable при запуске бота завершена")
            else:
                logger.info("Ежедневная синхронизация БД с Seatable завершена")
        except Exception as e:
            logger.error(f"Ошибка синхронизации: {str(e)}", exc_info=True)

    async def _scheduler_loop(self):
        """Цикл планировщика"""
        while True:
            now = datetime.utcnow()
            target_time = time.fromisoformat(Config.SYNC_TIME_UTC)
            next_run = datetime.combine(now.date(), target_time)

            if now >= next_run:
                next_run += timedelta(days=1)

            wait_seconds = (next_run - now).total_seconds()
            logger.info(f"Следующая синхронизация в {next_run} (UTC)")

            await asyncio.sleep(wait_seconds)
            await self.sync(startup=False)

    def start(self, loop: asyncio.AbstractEventLoop):
        """Запуск планировщика"""
        # Синхронизация при старте
        asyncio.create_task(self.sync(startup=True))

        # Ежедневная синхронизация
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info(f"Планировщик запущен. Ежедневная синхронизация в {Config.SYNC_TIME_UTC} UTC")


# Глобальный экземпляр планировщика
scheduler = Scheduler()


def start_sync(loop: asyncio.AbstractEventLoop):
    """Инициализация синхронизации"""
    scheduler.start(loop)