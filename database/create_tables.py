import asyncio
from sqlalchemy.ext.asyncio import AsyncEngine
from database import Base, engine

async def create_tables(engine: AsyncEngine):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(create_tables(engine))