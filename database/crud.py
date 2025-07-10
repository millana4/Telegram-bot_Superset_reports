from database import AsyncSessionLocal
from sqlalchemy import select
from database.models import User
from database.seatable_client import fetch_tables
from config import Config
from utils.phone import normalize_phone
import logging

logger = logging.getLogger(__name__)

async def insert_new_users():
    """Синхронизирует пользователей из SeaTable с БД PostgreSQL"""

    # Получаем данные из SeaTable
    sea_users_data = await fetch_tables(Config.SEATABLE_USERS_TABLE_ID)
    sea_groups_data = await fetch_tables(Config.SEATABLE_EMAIL_TABLE_ID)

    if not sea_users_data or not sea_groups_data:
        logger.error("Не удалось получить данные из одной из таблиц SeaTable.")
        return

    sea_users = sea_users_data.get("rows", [])
    sea_groups = sea_groups_data.get("rows", [])

    # Маппим user_id из users -> (phone, name, row_id)
    seatable_users_by_id = {}
    for u in sea_users:
        if not isinstance(u, dict):
            continue

        items = list(u.items())

        # Пропускаем, если нет хотя бы двух полей + _id
        if len(items) < 2 or "_id" not in u:
            continue

        # Предполагаем: 1-й — имя, 2-й — телефон
        name = items[0][1]
        phone_raw = items[1][1]
        phone = normalize_phone(phone_raw)

        if not phone:
            continue

        seatable_users_by_id[u["_id"]] = {
            "name": name,
            "phone": phone,
            "row_id": u["_id"]
        }

    # Маппим user_id -> email из второй таблицы
    emails_by_user_id = {}
    for g in sea_groups:
        if not isinstance(g, dict):
            continue

        items = list(g.items())

        # Ищем список с вложенными словарями
        group_links = next((v for k, v in items if isinstance(v, list) and v and isinstance(v[0], dict)), [])

        # Ищем email среди строковых значений, ключ которых не начинается с "_" (не служебные поля)
        email = next(
            (v for k, v in items if isinstance(v, str) and '@' in v and not k.startswith('_')),
            None
        )

        for link in group_links:
            if isinstance(link, dict) and "row_id" in link:
                emails_by_user_id[link["row_id"]] = email

    # Получаем все телефоны из PostgreSQL
    async with AsyncSessionLocal() as session:
        db_users_result = await session.stream(select(User.phone, User.id, User.phone, User.email))
        db_users = {normalize_phone(phone): uid for phone, uid, _, _ in (await db_users_result.fetchall())}

        db_phones_set = set(db_users.keys())
        sea_phones_set = set(user["phone"] for user in seatable_users_by_id.values())

        # Удаляем тех, кто есть в БД, но уже нет в SeaTable
        for phone in db_phones_set - sea_phones_set:
            result = await session.execute(select(User).where(User.phone == phone))
            user = result.scalar_one_or_none()
            if user:
                phone_value = user.phone
                await session.delete(user)
                logger.info(f'Отписали от уведомлений: {phone_value} (удалён из SeaTable)')

        # Добавляем новых
        added = 0
        for user_id, user_info in seatable_users_by_id.items():
            phone = user_info["phone"]
            name = user_info["name"]

            if phone in db_phones_set:
                continue  # Уже в БД

            email = emails_by_user_id.get(user_id)
            session.add(User(phone=phone, email=email))
            added += 1
            logger.info(f'Добавлен новый пользователь: {name}, телефон: {phone}, email: {email}')

        await session.commit()
        if added:
            logger.info(f"Добавлено {added} новых пользователей.")
        else:
            logger.info("Новые пользователи не найдены.")


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
