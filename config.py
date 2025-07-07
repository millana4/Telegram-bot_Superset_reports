import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_IDS = list(map(int, os.getenv("ADMIN_IDS").split(",")))

    TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")  # id чата или пользователя, куда пересылать сообщение

    IMAP_SERVER = os.getenv("IMAP_SERVER")
    IMAP_EMAIL = os.getenv("IMAP_EMAIL")
    IMAP_PASSWORD = os.getenv("IMAP_PASSWORD")

    ALLOWED_EMAIL_DOMAINS = ["votonia.ru", "mavis.ru"]

    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB")