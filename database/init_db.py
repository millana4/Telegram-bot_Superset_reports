# Скрипт для ручного добавления данных на этапе разработки
import asyncio
from database import AsyncSessionLocal, engine
from database.models import Base, User

async def async_main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)  # Удаляем все таблицы
        await conn.run_sync(Base.metadata.create_all)  # Создаём заново

    async with AsyncSessionLocal() as db:
        test_user = User(
            telegram_id=7319983726,
            phone="+79999999999",
            email="milua.mavis@gmail.com",
            last_uid=None,
        )
        db.add(test_user)
        await db.commit()
        print("Тестовый пользователь добавлен")

if __name__ == "__main__":
    asyncio.run(async_main())
    

