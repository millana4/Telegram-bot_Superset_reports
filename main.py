import asyncio
import aioimaplib
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from email import message_from_bytes
from config import Config
from database.crud import get_last_uid, update_last_uid

import logging

# Инициализация бота
bot = Bot(token=Config.BOT_TOKEN)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

dp = Dispatcher()

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """
    Приветствие при /start.
    В дальнейшем сюда добавится проверка телефона / кода.
    """
    await message.answer("Приветствуем! Вы подписались на уведомления от Superset.")
    logger.info("User %s нажал /start", message.from_user.id)


async def handle_email(email_msg):
    """Извлекает из письма тему и вложение"""
    try:
        # Декодируем тему письма (может быть в base64 или quoted-printable)
        from email.header import decode_header
        subject = email_msg.get('subject', 'Без темы')
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


async def imap_idle_listener():
    """Подключается к IMAP и слушает новые письма в режиме IDLE."""
    client = None
    try:
        logger.info(f"Подключаюсь к IMAP: {Config.IMAP_SERVER}")
        client = aioimaplib.IMAP4_SSL(Config.IMAP_SERVER)

        await client.wait_hello_from_server()
        logger.info("Сервер доступен")

        await client.login(Config.IMAP_EMAIL, Config.IMAP_PASSWORD)
        logger.info("Авторизация успешна")

        await client.select('INBOX')
        logger.info("Выбрана папка Входящие для работы")

        last_uid = await get_last_uid(Config.IMAP_EMAIL)
        logger.info(f"Последний обработанный UID: {last_uid}")

        while True:
            # Запускаем IDLE режим
            await client.idle_start()
            logger.info("IMAP: режим IDLE включён, ждём письмо")

            # Ждём уведомления от сервера
            response = await client.wait_server_push()
            logger.debug(f"IMAP PUSH: {response}")

            # Выходим из IDLE перед обработкой
            client.idle_done()
            logger.info("IMAP: получен EXISTS, вышли из IDLE")

            # Ищем непрочитанные письма (используем обычный SEARCH вместо UID SEARCH)
            status, data = await client.search('UNSEEN')
            logger.debug(f"SEARCH RESULT: status={status}, data={data}")

            if status == 'OK' and data and data[0]:
                for num in data[0].decode().split():
                    logger.info(f"Обработка письма №: {num}")

                    # Получаем UID письма
                    status, uid_data = await client.fetch(num, '(UID)')
                    if status != 'OK' or not uid_data:
                        logger.error(f"Ошибка получения UID для письма {num}")
                        continue

                    # Извлекаем UID из ответа
                    uid = None
                    for item in uid_data:
                        if isinstance(item, bytes) and b'UID' in item:
                            # Пример ответа: b'123 (UID 1023)'
                            uid_part = item.decode().split('UID')[-1].strip()
                            uid = uid_part.strip(')').strip()

                    if not uid:
                        logger.error(f"Не удалось извлечь UID для письма {num}")
                        continue

                    logger.debug(f"Извлечённый UID: {uid} (тип: {type(uid)})")

                    # Получаем содержимое письма
                    status, msg_data = await client.fetch(num, '(RFC822)')
                    if status != 'OK' or not msg_data:
                        logger.error(f"Ошибка получения письма {num}")
                        continue

                    # Собираем письмо из частей
                    raw_email = bytearray()
                    for item in msg_data:
                        if isinstance(item, (bytes, bytearray)):
                            # Пропускаем служебные строки
                            if b'FETCH' in item or b'FLAGS' in item:
                                continue
                            raw_email.extend(item)

                    if not raw_email:
                        logger.error(f"Не найдены данные письма {num}. Полный ответ:")
                        for i, item in enumerate(msg_data):
                            logger.error(f"Часть {i}: {type(item)} - {str(item)[:100]}")
                        continue

                    try:
                        email_msg = message_from_bytes(bytes(raw_email))
                        subject, attachments = await handle_email(email_msg)

                        if attachments:
                            # Сначала отправляем тему письма
                            await bot.send_message(
                                Config.TELEGRAM_CHAT_ID,
                                f"Вам пришел новый отчет от Superset — {subject}"
                            )

                            # Затем отправляем все PDF-вложения
                            for filename, payload in attachments:
                                with open("debug.pdf", "wb") as f:  # Для отладки
                                    f.write(payload)
                                logger.info(f"Сохранён debug.pdf для проверки")

                                await bot.send_document(
                                    Config.TELEGRAM_CHAT_ID,
                                    types.BufferedInputFile(payload, filename=filename)
                                )

                            await update_last_uid(Config.IMAP_EMAIL, uid)

                    except Exception as e:
                        logger.error(f"Ошибка обработки: {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Критическая ошибка: {e}", exc_info=True)
        raise
    finally:
        if client:
            try:
                await client.logout()  # Важно: await для logout
            except Exception as e:
                logger.error(f"Ошибка при выходе: {e}")


async def main():
    """
    Запускает два таска:
        1) Telegram‑бот (polling), чтобы обрабатывать команды пользователей      — dp.start_polling()
        2) IMAP‑слушатель                                                        — imap_idle_listener()
    """
    me = await bot.get_me()
    logger.info("Telegram bot @%s запущен", me.username)

    # параллельный запуск
    await asyncio.gather(
        dp.start_polling(bot),
        imap_idle_listener(),
    )


if __name__ == '__main__':
    asyncio.run(main())