import asyncio
from database import AsyncSessionLocal


async def test_db():
    async with AsyncSessionLocal() as db:
        result = await db.execute("SELECT 1")
        print("Тест запроса:", result.scalar())

        users = await db.execute("SELECT * FROM users")
        print("Пользователи в БД:", users.all())


asyncio.run(test_db())
