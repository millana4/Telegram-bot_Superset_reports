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
        "app_name":"users_sset-grp",
        "access_token":"some_token_string",
        "dtable_uuid":"54abc13e-2968-495b-b40d-b690775cd64f",
        "dtable_server":"https://tab.4xapp.ru/dtable-server/",
        "dtable_socket":"https://tab.4xapp.ru/",
        "dtable_db":"https://tab.4xapp.ru/dtable-db/",
        "workspace_id":1,
        "dtable_name":"users_sset-grp"
    }
    """
    now = time.time()
    cached = _token_cache["token_data"]
    cached_time = _token_cache["timestamp"]

    if cached and (now - cached_time) < _TOKEN_TTL:
        return cached

    url = "https://tab.4xapp.ru/api/v2.1/dtable/app-access-token/"
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


async def get_table_columns(table_name: str) -> Optional[Dict[str, str]]:
    """
    Получает отображение внутреннего имени колонки -> читаемое имя
    для указанной таблицы (users, mailboxes и др).
    Возвращает словарь: { "internal_column_name": "Readable Name", ... }
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



async def prepare_for_db() -> Dict[str, Any]:
    """
    Возвращает сокращенные словари, чтобы было удобно синхронизировать с Postgres
    {
        'mailboxes':
            [
                {
                    'description': 'дашборды по продажам',
                    'email': 'box01@mail.ru',
                    'name': 'sale',
                    'seatable_id': 'some_string'
                },
            ],
    'relations':
        [
            {
                'mailbox_seatable_id': 'some_string',
                'user_seatable_id': 'some_string'
            },
            {
                'mailbox_seatable_id': 'some_string',
                'user_seatable_id': 'some_string'
            },
        ],
    'users':
        [
            {
                'last_uid': None,
                'name': 'usertest01_seller',
                'phone': '+7981ХХХХХХХ',
                'seatable_id': 'some_string',
                'telegram_id': None
            },
        ]
    }
    """
    # Получаем данные из таблиц
    users_data = await fetch_table(Config.SEATABLE_USERS_TABLE_ID)
    mailboxes_data = await fetch_table(Config.SEATABLE_MAILBOXES_TABLE_ID)

    # Получаем метаданные таблиц (для совместимости)
    users_metadata = await get_table_columns(Config.SEATABLE_USERS_TABLE_ID)
    mailboxes_metadata = await get_table_columns(Config.SEATABLE_MAILBOXES_TABLE_ID)

    # Подготовка данных для пользователей и почтовых ящиков
    users_to_db = []
    mailboxes_to_db = []
    user_mailbox_relations = []

    # Обрабатываем почтовые ящики (новая структура)
    for mailbox in mailboxes_data:
        try:
            mailbox_dict = {
                'seatable_id': mailbox.get('_id', ''),
                'name': mailbox.get('Name', ''),  # Прямое обращение к полю Name
                'email': mailbox.get('email', ''),  # Прямое обращение к полю email
                'description': mailbox.get('description', None)  # Прямое обращение
            }
            mailboxes_to_db.append(mailbox_dict)

            # Собираем связи из почтовых ящиков (users в mailbox)
            for user_id in mailbox.get('users', []):
                user_mailbox_relations.append({
                    'user_seatable_id': user_id,
                    'mailbox_seatable_id': mailbox['_id']
                })

        except Exception as e:
            logger.error(f"Ошибка обработки почтового ящика {mailbox.get('_id')}: {str(e)}")
            continue

    # Обрабатываем пользователей (новая структура)
    for user in users_data:
        try:
            user_dict = {
                'seatable_id': user.get('_id', ''),
                'name': user.get('Name', ''),  # Прямое обращение к полю Name
                'phone': normalize_phone(user.get('phone', None)),  # Прямое обращение
                'telegram_id': None,
                'last_uid': None
            }

            # Проверяем обязательное поле phone
            if not user_dict['phone']:
                logger.warning(f"Пользователь {user_dict['name']} без телефона пропущен")
                continue

            users_to_db.append(user_dict)

            # Собираем связи из пользователей (mailboxes в user) - на случай если есть только здесь
            for mailbox_id in user.get('mailboxes', []):
                relation = {
                    'user_seatable_id': user['_id'],
                    'mailbox_seatable_id': mailbox_id
                }
                if relation not in user_mailbox_relations:  # избегаем дублирования
                    user_mailbox_relations.append(relation)

        except Exception as e:
            logger.error(f"Ошибка обработки пользователя {user.get('_id')}: {str(e)}")
            continue

    # Удаляем возможные дубликаты связей
    unique_relations = []
    seen_relations = set()

    for rel in user_mailbox_relations:
        rel_tuple = (rel['user_seatable_id'], rel['mailbox_seatable_id'])
        if rel_tuple not in seen_relations:
            seen_relations.add(rel_tuple)
            unique_relations.append(rel)

    return {
        'users': users_to_db,
        'mailboxes': mailboxes_to_db,
        'relations': unique_relations
    }



# Отладочный скрипт для вывода ответов json по API SeaTable
#
# if __name__ == "__main__":
#     async def main():
#         print("Первый вызов users:")
#         users_raw = await fetch_table("users")
#         pprint.pprint(users_raw)
#
#         print("\nМетаданные для users:")
#         users_columns = await get_table_columns("users")
#         pprint.pprint(list(users_columns.keys()) if users_columns else "Не получены")
#
#         print("\nВторой вызов mailboxes:")
#         mailboxes_raw = await fetch_table("mailboxes")
#         pprint.pprint(mailboxes_raw)
#
#         print("\nМетаданные для mailboxes:")
#         mailboxes_columns = await get_table_columns("mailboxes")
#         pprint.pprint(list(mailboxes_columns.keys()) if mailboxes_columns else "Не получены")
#
#         print("\nПодготовленные словари для БД:")
#         prepared = await prepare_for_db()
#         pprint.pprint(prepared)
#
#     asyncio.run(main())