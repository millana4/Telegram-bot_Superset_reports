import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")

    IMAP_SERVER = os.getenv("IMAP_SERVER")
    IMAP_EMAIL_SR03 = os.getenv("IMAP_EMAIL_SR03")
    IMAP_PASSWORD_SR03 = os.getenv("IMAP_PASSWORD_SR03")
    IMAP_EMAIL_SR04 = os.getenv("IMAP_EMAIL_SR04")
    IMAP_PASSWORD_SR04 = os.getenv("IMAP_PASSWORD_SR04")

    SEATABLE_API_TOKEN = os.getenv("SEATABLE_API_TOKEN")
    SEATABLE_SERVER = os.getenv("SEATABLE_SERVER")
    SEATABLE_USERS_TABLE_ID = os.getenv("SEATABLE_USERS_TABLE_ID")
    SEATABLE_MAILBOXES_TABLE_ID = os.getenv("SEATABLE_MAILBOXES_TABLE_ID")
    SEATABLE_T_CHATS_TABLE_ID = os.getenv("SEATABLE_T_CHATS_TABLE_ID")