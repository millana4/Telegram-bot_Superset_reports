import os
import time
import asyncio
import logging

from bot import bot
from aiogram.types import BufferedInputFile
from imap_tools import MailBox, AND
from email.header import decode_header

from sqlalchemy import select

from database import AsyncSessionLocal
from database.crud import update_last_uid, get_last_uid
from database.models import User, user_mailbox, Mailbox

logger = logging.getLogger(__name__)


async def handle_email(email_msg):
    """Извлекает из письма тему и вложения (только PDF и PNG файлы)"""
    try:
        # Декодируем тему письма
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
            # Пропускаем multipart-контейнеры
            if part.get_content_maintype() == 'multipart':
                continue

            content_disposition = str(part.get("Content-Disposition", "")).lower()
            filename = part.get_filename()

            # Если есть имя файла или явно указано, что это вложение
            if filename or 'attachment' in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if not payload:
                        continue

                    # Определяем расширение файла
                    file_extension = None

                    # Вариант 1: Из имени файла
                    if filename:
                        filename_lower = filename.lower()
                        logger.info(f'Имя файла {filename_lower}')
                        if filename_lower.endswith('.pdf'):
                            file_extension = '.pdf'
                        elif filename_lower.endswith('.png'):
                            file_extension = '.png'

                    # Вариант 2: Из content-type
                    if not file_extension:
                        content_type = part.get_content_type().lower()
                        if 'pdf' in content_type:
                            file_extension = '.pdf'
                        elif 'png' in content_type:
                            file_extension = '.png'

                    # Пропускаем если не PDF и не PNG
                    if not file_extension:
                        logger.warning(f"Пропущено вложение недопустимого типа: {filename}")
                        continue

                    # Создаем имя файла если его нет
                    if not filename:
                        filename = f"attachment_{int(time.time())}{file_extension}"
                    else:
                        # Убедимся, что у файла правильное расширение
                        if not filename.lower().endswith(file_extension):
                            filename = f"{os.path.splitext(filename)[0]}{file_extension}"

                    logger.info(f"Найдено вложение: {filename} ({len(payload)} bytes)")
                    attachments.append((filename, payload))

                except Exception as e:
                    logger.error(f"Ошибка обработки вложения {filename}: {e}")

        logger.info(f"Итого найдено PDF/PNG вложений: {len(attachments)}")
        return subject, attachments

    except Exception as e:
        logger.error(f"Критическая ошибка в handle_email: {e}", exc_info=True)
        raise

async def distribute_attachments(email: str, subject: str, attachments: list[tuple[str, bytes]], loop: asyncio.AbstractEventLoop):
    """Принимает файл, обращается к БД, ищет список пользователей и отправляем им файл"""
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(User.telegram_id)
            .join(user_mailbox)
            .join(Mailbox)
            .where(Mailbox.email == email)
            .where(User.telegram_id.isnot(None))
        )
        telegram_ids = [row[0] for row in result.all()]

        if not telegram_ids:
            logger.info(f"[{email}] Нет подписчиков для рассылки.")
            return

        for telegram_id in telegram_ids:
            for filename, content in attachments:
                try:
                    await bot.send_document(
                        chat_id=telegram_id,
                        document=BufferedInputFile(content, filename=filename),
                        caption=subject if subject else None
                    )
                    logger.info(f"[{email}] Отправлено пользователю {telegram_id}: {filename}")
                except Exception as e:
                    logger.error(f"[{email}] Ошибка отправки пользователю {telegram_id}: {e}")


async def resend_report(message, account_email: str, loop: asyncio.AbstractEventLoop):
    """Запускает пересылку PDF-вложения и запускает обновление last_uid (последнего обработанного письма)"""
    try:
        print(f"[{account_email}] Обработка письма UID={message.uid}, тема: {message.subject}")

        # Обработка письма и извлечение данных
        subject, attachments = await handle_email(message.obj)

        # Пересылка пользователям из БД
        if attachments:
            await distribute_attachments(account_email, subject, attachments, loop)

            # Обновляем last_uid, если вложения были успешно отправлены
            await update_last_uid(account_email, str(message.uid))
        else:
            print(f"[{account_email}] Вложений нет, рассылка не требуется.")

    except Exception as e:
        print(f"[{account_email}] Ошибка обработки письма UID={message.uid}: {e}")


def imap_idle_listener(account, loop):
    """Слушает входящие письма на одном аккаунте через IMAP IDLE."""
    while True:
        try:
            with MailBox(account["imap"]).login(account["email"], account["password"]) as mailbox:
                mailbox.folder.set('INBOX')
                print(f"[{account['email']}] Подключен, выбрана папка INBOX. Ожидание писем...")

                while True:
                    print(f"[{account['email']}] Вошли в режим IDLE")
                    for _ in mailbox.idle.wait(timeout=300):  # Ждём новые письма до 5 минут
                        break

                    # Получаем все непрочитанные письма
                    messages = list(mailbox.fetch(AND(seen=False)))

                    if not messages:
                        print(f"[{account['email']}] Нет непрочитанных писем. Ожидание новых.")
                        continue

                    # Получаем последний обработанный UID
                    last_uid = asyncio.run_coroutine_threadsafe(
                        get_last_uid(account['email']), loop
                    ).result()

                    # Преобразуем к int, если значение есть
                    last_uid = int(last_uid) if last_uid is not None else None

                    if last_uid is None:
                        # Обрабатываем только самое свежее письмо
                        latest_message = max(messages, key=lambda m: int(m.uid))
                        print(f"[{account['email']}] Первая инициализация. Обрабатываем письмо UID={latest_message.uid}")

                        asyncio.run_coroutine_threadsafe(
                            resend_report(latest_message, account['email'], loop),
                            loop
                        )
                        # После обработки обновим last_uid
                        asyncio.run_coroutine_threadsafe(
                            update_last_uid(account['email'], str(latest_message.uid)), loop
                        )
                        continue

                    # Фильтруем только новые письма
                    unseen_messages = [m for m in messages if int(m.uid) > last_uid]

                    if not unseen_messages:
                        print(f"[{account['email']}] Новых непрочитанных писем нет.")
                        continue

                    # Сортируем по UID (на всякий случай)
                    unseen_messages.sort(key=lambda m: int(m.uid))

                    # Обрабатываем каждое новое письмо
                    for message in unseen_messages:
                        asyncio.run_coroutine_threadsafe(
                            resend_report(message, account['email'], loop),
                            loop
                        )

        except Exception as e:
            print(f"[{account['email']}] Ошибка подключения или работы с IMAP: {e}")
            time.sleep(10)
