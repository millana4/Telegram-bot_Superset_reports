import asyncio
import pprint
import time
import aiohttp
import logging
from typing import List, Dict, Optional, Any

from config import Config
from utils import normalize_phone

logger = logging.getLogger(__name__)

# Глобальный кэш токена
_token_cache: Dict[str, Optional[Dict]] = {
    "token_data": None,
    "timestamp": 0
}
_TOKEN_TTL = 172800  # время жизни токена в секундах — 48 часов


async def get_base_token() -> Optional[Dict]:
    """
    Получает временный токен для синхронизации по Апи.
    Возвращает словарь:
    {
        "app_name":"app_bot",
        "access_token":"some_token_string",
        "dtable_uuid":"54abc13e-2968-495b-b40d-b690775cd64f",
        "dtable_server":"server/dtable-server/",
        "dtable_socket":"server",
        "dtable_db":"server/dtable-db/",
        "workspace_id":1,
        "dtable_name":"users_sset-grp"
    }
    """
    now = time.time()
    cached = _token_cache["token_data"]
    cached_time = _token_cache["timestamp"]

    if cached and (now - cached_time) < _TOKEN_TTL:
        return cached

    url = f"{Config.SEATABLE_SERVER}/api/v2.1/dtable/app-access-token/"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {Config.SEATABLE_API_TOKEN}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                token_data = await response.json()
                logger.debug("Base token successfully obtained and cached")

                # Обновляем кэш
                _token_cache["token_data"] = token_data
                _token_cache["timestamp"] = now

                return token_data

    except aiohttp.ClientError as e:
        logger.error(f"API request failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

    return None


async def check_id_telegram(id_telegram: str) -> bool:
    """
    Проверяет наличие telegram_id в таблице Users.
    Возвращает True если пользователь найден, False если нет.
    """
    try:
        token_data = await get_base_token()
        if not token_data:
            logger.error("Не удалось получить токен SeaTable")
            return False

        base_url = f"{token_data['dtable_server']}api/v1/dtables/{token_data['dtable_uuid']}/rows/"
        headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        params = {"table_name": Config.SEATABLE_USERS_TABLE_ID}

        async with aiohttp.ClientSession() as session:
            async with session.get(base_url, headers=headers, params=params) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logger.error(f"Ошибка запроса: {response.status}. Ответ: {error_text}")
                    return False

                data = await response.json()
                """
                Пример data:
                {'rows': 
                    [
                        {'_id': 'HiQYOMv4SLSsSMF_EpGpOg', 
                        '_mtime': '2025-07-31T11:52:03.380+00:00', 
                        '_ctime': '2025-07-08T11:58:08.914+00:00', 
                        'Name': 'usertest01_seller', 
                        'phone': '+7981ХХХХХХХ', 
                        'mailboxes': ['Rp5djUppTcqM1LQO_3x_gg', 'FrwMkbJJSfejzUb7a6RdoQ']
                        },
                    ]
                """

                # Ищем пользователя с совпадающим id_telegram
                for row in data.get("rows", []):
                    if str(row.get("id_telegram")) == str(id_telegram):
                        logger.info(f"Найден пользователь с id_telegram: {id_telegram}")
                        return True

                logger.info(f"Пользователь с id_telegram {id_telegram} не найден")
                return False

    except Exception as e:
        logger.error(f"Ошибка при проверке пользователя: {str(e)}", exc_info=True)
        return False


async def register_id_telegram(phone: str, id_telegram: str) -> bool:
    """Обращается по API к Seatable, ищет там пользователя по телефону и записывает его id_telegram."""
    try:
        # Получаем токен
        token_data = await get_base_token()
        if not token_data:
            logger.error("Не удалось получить токен SeaTable")
            return False

        base_url = f"{token_data['dtable_server']}api/v1/dtables/{token_data['dtable_uuid']}/rows/"
        headers = {
            "Authorization": f"Bearer {token_data['access_token']}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        # Используем человекочитаемые названия колонок, а не их внутренние ключи
        phone_column = "phone"  # Колонка с телефонами
        id_telegram_column = "id_telegram"  # Колонка для id_telegram

        # Получаем параметры
        params = {
            "table_name": Config.SEATABLE_USERS_TABLE_ID,
            "convert_keys": "false"
        }

        async with aiohttp.ClientSession() as session:
            # Запрашиваем все строки
            async with session.get(base_url, headers=headers, params=params) as resp:
                if resp.status != 200:
                    logger.error(f"Ошибка получения данных: {resp.status}")
                    return False

                data = await resp.json()
                rows = data.get("rows", [])

                for row in rows[:5]:
                    raw_phone = str(row.get(phone_column, "N/A"))
                    logger.debug(f"- Исходный: '{raw_phone}' | Нормализованный: '{normalize_phone(raw_phone)}'")

                # Ищем точное совпадение
                matched_row = None
                for row in rows:
                    if phone_column in row:
                        # Нормализуем телефон из таблицы перед сравнением
                        row_phone_normalized = normalize_phone(str(row[phone_column]))
                        if row_phone_normalized == phone:
                            matched_row = row
                            break

                if not matched_row:
                    logger.error("Совпадений не найдено. Проверьте:")
                    logger.error(
                        f"- Номер {phone} в таблице: {[normalize_phone(str(r.get(phone_column, ''))) for r in rows if phone_column in r]}")
                    logger.error(f"- Колонка телефон: {phone_column}")
                    return False

                row_id = matched_row.get("_id")
                if not row_id:
                    logger.error("У строки нет ID")
                    return False

                logger.info(f"Найдена строка пользователя для обновления (ID: {row_id})")

                # Подготовка обновления
                update_data = {
                    "table_name": Config.SEATABLE_USERS_TABLE_ID,
                    "row_id": row_id,
                    "row": {
                        id_telegram_column: str(id_telegram)
                    }
                }

                # Отправка обновления
                async with session.put(base_url, headers=headers, json=update_data) as resp:
                    if resp.status != 200:
                        logger.error(f"Ошибка обновления: {resp.status} - {await resp.text()}")
                        return False

                    logger.info(f"ID Telegram успешно добавлен для пользователя с телефоном {phone}")
                    return True

    except Exception as e:
        logger.error(f"Критическая ошибка: {str(e)}", exc_info=True)
        return False


# Пока не используется, но может пригодиться
async def get_table_columns(table_name: str) -> Optional[Dict[str, str]]:
    """
    Получает отображение внутреннего имени колонки в виде словаря:
    {'0000': 'Name', 'Cv8Z': 'phone', 'KqFx': 'mailboxes', 'fz8p': 'id_telegram'}
    """
    token_data = await get_base_token()
    if not token_data:
        logger.error("Не удалось получить токен SeaTable")
        return []

    access_token = token_data["access_token"]
    dtable_uuid = token_data["dtable_uuid"]
    base_url = token_data["dtable_server"].rstrip("/")

    url = f"{base_url}/api/v1/dtables/{dtable_uuid}/columns/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    params = {"table_name": table_name}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                response.raise_for_status()
                metadata = await response.json()

                # Для отладки можно вывести в консоль полный ответ по метаданным
                # print("metadata type:", type(metadata))
                # print("metadata sample:", metadata)

                column_map = {col["key"]: col["name"] for col in metadata.get("columns", [])}
                return column_map

    except aiohttp.ClientError as e:
        logger.error(f"Ошибка при запросе метаданных таблицы {table_name}: {str(e)}")
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при получении колонок таблицы {table_name}: {str(e)}")

    return None



async def fetch_table(table_name: str) -> List[Dict]:
    """
    Получает строки из указанной таблицы Seatable (users или mailboxes).
    Возвращает список словарей.
    Пример словаря для users:
    [
        {
            'Name': 'usertest01_seller',
            '_ctime': '2025-07-08T11:58:08.914+00:00',
            '_id': 'id_text_format',
            '_mtime': '2025-07-14T13:59:10.958+00:00',
            'mailboxes': ['id_text_format'],
            'phone': '+7981ХХХХХХХ'
        },
    ]
    Пример словаря для mailboxes:
    [
        {
            'Name': 'sale',
            '_ctime': '2025-07-08T12:06:44.441+00:00',
            '_id': 'id_text_format',
            '_mtime': '2025-07-14T14:03:12.951+00:00',
            'description': 'дашборды по продажам',
            'email': 'box1@mail.ru',
            'users': ['id_text_format', 'id_text_format']
        },
    ]
    """

    token_data = await get_base_token()
    if not token_data:
        logger.error("Не удалось получить токен SeaTable")
        return []

    access_token = token_data["access_token"]
    dtable_uuid = token_data["dtable_uuid"]
    base_url = token_data["dtable_server"].rstrip("/")

    url = f"{base_url}/api/v1/dtables/{dtable_uuid}/rows/"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    params = {"table_name": table_name}

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"Ошибка запроса данных из таблицы '{table_name}': {response.status} - {error}")
                    return []

                data = await response.json()
                return data.get("rows", [])

    except Exception as e:
        logger.error(f"Ошибка запроса к Seatable: {str(e)}")
        return []


async def get_last_uid(email: str) -> str | None:
    """Получает last_uid (id последнего обработанного в рассылке письма) из таблицы Mailbox по email"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Mailbox.last_uid).where(Mailbox.email == email)
            )
            return result.scalar_one_or_none()
    except Exception as e:
        logger.error(f"Ошибка получения last_uid: {e}")
        raise


async def update_last_uid(email: str, uid: str):
    """Обновляет last_uid для Mailbox"""
    try:
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(Mailbox).where(Mailbox.email == email)
            )
            mailbox = result.scalar_one_or_none()
            if mailbox:
                mailbox.last_uid = uid
                await session.commit()
                logger.debug(f"[{email}] last_uid обновлён: {uid}")
    except Exception as e:
        logger.error(f"Ошибка обновления last_uid: {e}")
        raise

# Отладочный скрипт для вывода ответов json по API SeaTable
# if __name__ == "__main__":
#     async def main():
#         print("Базовый токен")
#         token_data = await get_base_token()
#         print(token_data)
#
#         print("Таблица пользователей, шапка:")
#         user_table = await get_table_columns(Config.SEATABLE_USERS_TABLE_ID)
#         print(user_table)
#
#     asyncio.run(
#         main())