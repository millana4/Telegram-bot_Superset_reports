from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from database.models import Base
from config import Config
import logging

# Async PostgreSQL URL
config = Config()
DATABASE_URL = f"postgresql+asyncpg://{config.POSTGRES_USER}:{config.POSTGRES_PASSWORD}@{config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB}"

logger = logging.getLogger(__name__)

# Настройка асинхронного движка
engine = create_async_engine(
    DATABASE_URL,
    echo=False, # Логирование через нашу систему
    poolclass=NullPool  # Отключаем пул для асинхронной работы
)

# Асинхронная сессия
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session