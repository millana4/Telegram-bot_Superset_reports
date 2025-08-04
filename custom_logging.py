import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging():
    """Настройка логирования для всего проекта"""
    # Создаем папку для логов
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    # Основные настройки
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Формат логов
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Файловый обработчик (ротация каждые 5 МБ)
    file_handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setFormatter(formatter)

    # Консольный обработчик
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Добавляем обработчики
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    # Логирование для библиотек
    logging.getLogger('aiogram').setLevel(logging.INFO)
    logging.getLogger('sqlalchemy').setLevel(logging.INFO)