from unicodedata import normalize

from database import AsyncSessionLocal
from sqlalchemy import select
from database.models import User
from utils.phone import normalize_phone
import logging

logger = logging.getLogger(__name__)

async def insert_new_users(rows):
    """Добавляет в базу данных новых пользователей из SeaTable"""
    async with AsyncSessionLocal() as session:
        # ждём результат stream()
        result = await session.stream(select(User.phone))

        # уже по result идём async‑циклом
        db_phones = {r[0] async for r in result}

        added = 0
        for row in rows:
            raw_phone = row["phone"]
            phone = normalize_phone(raw_phone)

            if not phone or phone in db_phones:
                continue  # пустой или уже есть

            session.add(User(phone=phone))
            added += 1

        if added:
            await session.commit()
            logger.info("В базу добавлено %s новых пользователей", added)
        else:
            logger.info("Сегодня новые пользователи не добавлены")


async def get_last_uid(email: str) -> str | None:
    """Получает последний обработанный UID письма в ящике"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(User).where(User.email == email))
            user = result.scalar_one_or_none()

            if user:
                logger.debug(f"Найден last_uid для {email}: {user.last_uid}")
                return user.last_uid
            logger.warning(f"Пользователь с email {email} не найден")
            return None

    except Exception as e:
        logger.error(f"Ошибка при получении last_uid: {e}")
        raise


async def update_last_uid(email: str, last_uid: str) -> None:
    """Обновляет последний обработанный UID для ящика"""
    try:
        async with AsyncSessionLocal() as session:
            # Получаем пользователя и блокируем запись для обновления
            result = await session.execute(
                select(User)
                .where(User.email == email)
                .with_for_update()
            )
            user = result.scalar_one_or_none()

            if not user:
                logger.error(f"Пользователь с email {email} не найден")
                return

            old_uid = user.last_uid
            user.last_uid = last_uid

            # Явно добавляем пользователя в сессию
            session.add(user)
            await session.commit()
            logger.info(f"UID обновлён для {email}: {old_uid} -> {last_uid}")

    except Exception as e:
        logger.error(f"Ошибка при обновлении last_uid: {e}")
        if 'session' in locals():
            await session.rollback()
        raise
