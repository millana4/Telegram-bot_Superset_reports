from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BTN_SHARE_CONTACT = "☎️ Поделиться контактом"

share_contact_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_SHARE_CONTACT, request_contact=True)]],
    resize_keyboard=True,
    one_time_keyboard=True,
)