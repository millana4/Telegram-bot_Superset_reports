from aiogram.dispatcher.middlewares.base import BaseMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Callable, Awaitable, Dict, Any
from database import AsyncSessionLocal

class DbSessionMiddleware(BaseMiddleware):
    async def __call__(self,
                       handler: Callable[[Any, Dict[str, Any]], Awaitable[Any]],
                       event: Any,
                       data: Dict[str, Any]) -> Any:
        async with AsyncSessionLocal() as session:
            data["session"] = session  # <- передаём session в хендлер
            return await handler(event, data)