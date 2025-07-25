import asyncio
from sqlalchemy.exc import IntegrityError
from sqlalchemy import delete, insert

from database import AsyncSessionLocal
from sqlalchemy import select, update

from database.models import User, Mailbox, user_mailbox
from database.seatable_api import prepare_for_db
import logging

logger = logging.getLogger(__name__)


async def sync_users():
    """Синхронизирует пользователей и почтовые ящики из SeaTable с PostgreSQL"""

    # Получаем данные из SeaTable
    data = await prepare_for_db()
    if not data:
        logger.error("Не удалось получить данные из SeaTable")
        return False

    async with AsyncSessionLocal() as session:
        try:
            # --- Обработка почтовых ящиков ---
            logger.info("Начинаем синхронизацию почтовых ящиков...")
            db_mailboxes = {m.seatable_id: m for m in (await session.execute(select(Mailbox))).scalars()}
            sea_mailbox_ids = {m['seatable_id'] for m in data['mailboxes']}

            to_delete_mailboxes = set(db_mailboxes.keys()) - sea_mailbox_ids
            if to_delete_mailboxes:
                await session.execute(delete(Mailbox).where(Mailbox.seatable_id.in_(to_delete_mailboxes)))
                logger.info(f"Удалено мейлбоксов: {len(to_delete_mailboxes)}")

            for mailbox_data in data['mailboxes']:
                mailbox = db_mailboxes.get(mailbox_data['seatable_id'])
                if not mailbox:
                    mailbox = Mailbox(
                        seatable_id=mailbox_data['seatable_id'],
                        name=mailbox_data['name'],
                        email=mailbox_data['email'],
                        description=mailbox_data['description'],
                        last_uid = None
                    )
                    session.add(mailbox)
                    logger.info(f"Добавлен мейлбокс: {mailbox.email}")
                else:
                    if any([
                        mailbox.name != mailbox_data['name'],
                        mailbox.email != mailbox_data['email'],
                        mailbox.description != mailbox_data['description']
                    ]):
                        mailbox.name = mailbox_data['name']
                        mailbox.email = mailbox_data['email']
                        mailbox.description = mailbox_data['description']
                        logger.info(f"Обновлен мейлбокс: {mailbox.email}")

            # --- Обработка пользователей ---
            logger.info("Начинаем синхронизацию пользователей...")
            db_users = {u.seatable_id: u for u in (await session.execute(select(User))).scalars()}
            sea_user_ids = {u['seatable_id'] for u in data['users']}

            to_delete_users = set(db_users.keys()) - sea_user_ids
            if to_delete_users:
                await session.execute(delete(User).where(User.seatable_id.in_(to_delete_users)))
                logger.info(f"Удалено пользователей: {len(to_delete_users)}")

            for user_data in data['users']:
                if not user_data.get('phone'):
                    logger.warning(f"Пользователь {user_data.get('name')} не добавлен — отсутствует номер телефона")
                    continue
                user = db_users.get(user_data['seatable_id'])
                if not user:  # если пользователя еще нет в БД, то добавляем
                    user = User(
                        seatable_id=user_data['seatable_id'],
                        name=user_data['name'],
                        phone=user_data['phone'],
                        telegram_id=None,
                    )
                    try:
                        session.add(user)
                        await session.flush()  # Пробуем записать в базу сразу, чтобы отловить IntegrityError на этом этапе
                        logger.info(f"Добавлен пользователь: {user.name}")
                    except IntegrityError:
                        await session.rollback()
                        logger.warning(
                            f"Пропущен пользователь при добавлении в БД — {user_data.get('name')} с seatable_id={user_data.get('seatable_id')} "
                            f"У него дублирующий телефон: {user_data.get('phone')}. Нужно убрать дублирование в Seatable"
                        )
                else:
                    if any([
                        user.name != user_data['name'],
                        user.phone != user_data['phone']
                    ]):
                        user.name = user_data['name']
                        user.phone = user_data['phone']
                        logger.info(f"Обновлен пользователь: {user.name}")

            # --- Обработка связей ---
            logger.info("Обновляем связи пользователей и мейлбоксов...")
            await session.execute(delete(user_mailbox))

            # Подгружаем ID пользователей и мейлбоксов
            users_map = {u.seatable_id: u.id for u in (await session.execute(select(User))).scalars()}
            mailboxes_map = {m.seatable_id: m.id for m in (await session.execute(select(Mailbox))).scalars()}

            links = []
            for relation in data['relations']:
                user_id = users_map.get(relation['user_seatable_id'])
                mailbox_id = mailboxes_map.get(relation['mailbox_seatable_id'])
                if user_id and mailbox_id:
                    links.append({'user_id': user_id, 'mailbox_id': mailbox_id})
                    logger.debug(f"Связали пользователя {user_id} с мейлбоксом {mailbox_id}")

            if links:
                await session.execute(insert(user_mailbox), links)

            await session.commit()
            logger.info("Синхронизация успешно завершена!")
            return True

        except IntegrityError as e:
            await session.rollback()
            logger.error(f"Ошибка целостности данных: {str(e)}")
        except Exception as e:
            await session.rollback()
            logger.error(f"Ошибка при синхронизации: {str(e)}")

        return False

async def get_last_uid(email: str) -> str | None:
    """Получает last_uid (id последнего обработанного в рассылке письма) из таблицы Mailbox по email"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Mailbox.last_uid).where(Mailbox.email == email)
            )
            return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения last_uid: {e}")
        raise


async def update_last_uid(email: str, uid: str):
    """Обновляет last_uid для Mailbox"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Mailbox).where(Mailbox.email == email)
            )
            mailbox = result.scalar_one_or_none()
            if mailbox:
                mailbox.last_uid = uid
                await session.commit()
                logger.debug(f"[{email}] last_uid обновлён: {uid}")
    except Exception as e:
        logger.error(f"Ошибка обновления last_uid: {e}")
        raise


# Скрипт для отладки sync_users().
# Запускает синхронизацию, обновляет данные в БД — данные пользователей, мейлбоксов, связи
# if __name__ == "__main__":
#     asyncio.run(sync_users())