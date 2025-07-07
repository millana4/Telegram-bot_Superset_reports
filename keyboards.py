from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

BTN_START = "🚀 Старт"

start_kb = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text=BTN_START)]],
    resize_keyboard=True,
    one_time_keyboard=True,     # исчезнет после нажатия
)