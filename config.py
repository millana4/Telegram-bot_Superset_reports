import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    IMAP_SERVER = os.getenv("IMAP_SERVER")
    IMAP_EMAIL_SR01 = os.getenv("IMAP_EMAIL_SR01")
    IMAP_PASSWORD_SR01 = os.getenv("IMAP_PASSWORD_SR01")
    IMAP_EMAIL_SR02 = os.getenv("IMAP_EMAIL_SR02")
    IMAP_PASSWORD_SR02 = os.getenv("IMAP_PASSWORD_SR02")

    POSTGRES_USER = os.getenv("POSTGRES_USER")
    POSTGRES_PASSWORD = os.getenv("POSTGRES_PASSWORD")
    POSTGRES_HOST = os.getenv("POSTGRES_HOST", "localhost")
    POSTGRES_PORT = os.getenv("POSTGRES_PORT", "5432")
    POSTGRES_DB = os.getenv("POSTGRES_DB")

    SEATABLE_API_URL = os.getenv("SEATABLE_API_URL")
    SEATABLE_API_TOKEN = os.getenv("SEATABLE_API_TOKEN")
    SEATABLE_USERS_TABLE_ID = os.getenv("SEATABLE_USERS_TABLE_ID")
    SEATABLE_MAILBOXES_TABLE_ID = os.getenv("SEATABLE_MAILBOXES_TABLE_ID")
    SYNC_TIME_UTC = os.getenv("SYNC_TIME_UTC")