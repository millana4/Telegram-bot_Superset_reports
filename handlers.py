from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardRemove
import logging

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User
from utils import normalize_phone
from keyboards import share_contact_kb


logger = logging.getLogger(__name__)
router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message, session: AsyncSession):
    """Обработчик нажатия кнопки Старт"""
    telegram_id = message.from_user.id
    logger.info("User %s нажал кнопку Старт", telegram_id)

    # Проверяем, есть ли пользователь с таким telegram_id
    result = await session.execute(select(User).where(User.telegram_id == telegram_id))
    user = result.scalar_one_or_none()

    if user:
        await message.answer("👋 Приветствуем! Вы подписаны на уведомления от Superset.")
        return

    # Иначе просим поделиться контактом
    await message.answer(
        "Поделитесь, пожалуйста, вашим контактом — номером телефона, чтобы авторизоваться в системе.",
        reply_markup=share_contact_kb,
    )


@router.message(F.contact)
async def handle_contact(message: types.Message, session: AsyncSession):
    """Обработка контакта для авторизации"""
    contact = message.contact
    telegram_id = message.from_user.id

    normalized_phone = normalize_phone(contact.phone_number)
    logger.info("Пользователь прислал номер: %s (нормализован: %s)", contact.phone_number, normalized_phone)

    # Ищем пользователя по номеру
    result = await session.execute(select(User).where(User.phone == normalized_phone))
    user = result.scalar_one_or_none()

    if user:
        # Обновляем telegram_id
        await session.execute(
            update(User).where(User.id == user.id).values(telegram_id=telegram_id)
        )
        await session.commit()
        await message.answer(
            "👋 Приветствуем! Вы подписались на уведомления от Superset.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            "🚫 Ваш номер телефона не найден в системе. Обратитесь к администратору.",
            reply_markup=ReplyKeyboardRemove()
        )

