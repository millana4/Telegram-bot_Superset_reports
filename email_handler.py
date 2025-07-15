import time
import asyncio
import logging
from imap_tools import MailBox, AND
from email.header import decode_header


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def handle_email(email_msg):
    """Извлекает из письма тему и вложение"""
    try:
        # Декодируем тему письма (может быть в base64 или quoted-printable)
        subject = email_msg['Subject'] or 'Без темы'
        decoded_subject = []
        for part, encoding in decode_header(subject):
            if isinstance(part, bytes):
                decoded_subject.append(part.decode(encoding or 'utf-8'))
            else:
                decoded_subject.append(str(part))
        subject = ' '.join(decoded_subject)
        logger.info(f"Тема письма: {subject}")

        attachments = []

        # Перебираем все части письма
        for part in email_msg.walk():
            content_type = part.get_content_type()
            filename = part.get_filename()
            content_disposition = str(part.get('Content-Disposition')) # Является ли вложением или встроено в контент

            logger.debug(f"Часть письма: Type={content_type}, File={filename}, Disposition={content_disposition}")

            # Проверяем, является ли часть вложением
            if (part.get_content_maintype() != 'multipart' and
                    'attachment' in content_disposition.lower()):
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        logger.info(f"Найдено вложение: {filename} ({len(payload)} bytes)")

                        # Проверяем PDF (по content-type или расширению файла)
                        if (content_type == 'application/pdf' or
                                (filename and filename.lower().endswith('.pdf'))):
                            attachments.append((filename, payload))
                            logger.info(f"Добавлен PDF: {filename}")
                        else:
                            logger.warning(f"Пропущено не-PDF вложение: {filename}")
                except Exception as e:
                    logger.error(f"Ошибка обработки вложения {filename}: {e}")

        logger.info(f"Итого найдено PDF вложений: {len(attachments)}")
        return subject, attachments

    except Exception as e:
        logger.error(f"Критическая ошибка в handle_email: {e}", exc_info=True)
        raise

def imap_idle_listener(account, loop):
    """Слушает входящие письма на одном аккаунте через IMAP IDLE."""
    while True:
        try:
            with MailBox(account["imap"]).login(account["email"], account["password"]) as mailbox:
                mailbox.folder.set('INBOX')
                print(f"[{account['email']}] Подключен, выбрана папка INBOX. Ожидание писем...")

                while True:
                    print(f"[{account['email']}] Вошли в режим IDLE")
                    for _ in mailbox.idle.wait(timeout=300):  # принимает уведомления отсервера
                        break

                    # После выхода из IDLE — ищем непрочитанные письма
                    unseen_messages = list(mailbox.fetch(criteria=AND(seen=False)))

                    if not unseen_messages:
                        print(f"[{account['email']}] Новых непрочитанных писем нет.")
                        continue

                    for message in unseen_messages:
                        try:
                            print(f"[{account['email']}] Обработка письма UID={message.uid}, тема: {message.subject}")
                            asyncio.run_coroutine_threadsafe(handle_email(message.obj), loop)
                        except Exception as e:
                            print(f"[{account['email']}] Ошибка обработки письма UID={message.uid}: {e}")
        except Exception as e:
            print(f"[{account['email']}] Ошибка подключения или работы с IMAP: {e}")
            time.sleep(10)