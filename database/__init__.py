from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from .models import Base
from config import Config

# Async PostgreSQL URL
config = Config()
DATABASE_URL = f"postgresql+asyncpg://{config.POSTGRES_USER}:{config.POSTGRES_PASSWORD}@{config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB}"

# Настройка асинхронного движка
engine = create_async_engine(
    DATABASE_URL,
    echo=True,  # Логирование запросов (False в продакшене)
    poolclass=NullPool  # Отключаем пул для асинхронной работы
)

# Асинхронная сессия
AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session