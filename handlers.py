from aiogram import Router, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import ReplyKeyboardRemove
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from utils import normalize_phone
from keyboards import share_contact_kb
from seatable_api import check_id_telegram, register_id_telegram


logger = logging.getLogger(__name__)
router = Router()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработчик нажатия кнопки Старт"""
    id_telegram = message.from_user.id
    logger.info("Пользователь %s нажал кнопку Старт", id_telegram)

    # Проверяем, есть ли пользователь с таким id_telegram
    already_member = await check_id_telegram(id_telegram)
    logger.info(f"Пользователь %s есть в таблице Seatable — {already_member}", id_telegram)

    if already_member:
        await message.answer("👋 Приветствуем! Вы подписаны на уведомления от Superset.")
        return

    # Иначе просим поделиться контактом
    await message.answer(
        "Поделитесь, пожалуйста, вашим контактом — номером телефона, чтобы авторизоваться в системе.",
        reply_markup=share_contact_kb,
    )


@router.message(F.contact)
async def handle_contact(message: types.Message):
    """Обработка контакта для авторизации"""
    contact = message.contact
    id_telegram = message.from_user.id

    normalized_phone = normalize_phone(contact.phone_number)
    logger.info("Пользователь прислал номер: %s (нормализован: %s)", contact.phone_number, normalized_phone)

    # Добавляем id_telegram пользователя в таблицу Seatable
    success = await register_id_telegram(normalized_phone, id_telegram)

    if success:
        await message.answer(
            "👋 Приветствуем! Вы подписались на уведомления от Superset.",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await message.answer(
            "🚫 Ваш номер телефона не найден в системе. Обратитесь к администратору.",
            reply_markup=ReplyKeyboardRemove()
        )

