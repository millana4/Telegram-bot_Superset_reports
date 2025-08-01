from aiogram import Router
from aiogram.types import ChatMemberUpdated
import logging

from seatable_api import register_group

router = Router()
logger = logging.getLogger(__name__)

@router.my_chat_member()
async def on_my_chat_member_updated(event: ChatMemberUpdated):
    logger.info(f"Получено событие my_chat_member: {event.model_dump()}")

    if (event.old_chat_member.status in ("left", "kicked") and
            event.new_chat_member.status in ("member", "administrator", "creator") and
            event.new_chat_member.user.id == event.bot.id):

        chat_id = event.chat.id
        chat_title = event.chat.title

        logger.info(f"Бот добавлен в группу: {chat_title} (ID: {chat_id})")

        try:
            success = await register_group(chat_id, chat_title)
            if not success:
                logger.error("Не удалось зарегистрировать группу в Seatable")
        except Exception as e:
            logger.error(f"Ошибка при регистрации группы: {str(e)}", exc_info=True)
    else:
        logger.info("Событие не соответствует условиям обработки")