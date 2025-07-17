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
        "app_name": "ssetuser",
        "access_token": "some_token_string",
        "dtable_uuid": "4cacfb1a-7d69-45ec-b181-952b913e1483",
        "workspace_id": 82533,
        "dtable_name": "users_sset-grp",
        "use_api_gateway": true,
        "dtable_server": "https://cloud.seatable.io/api-gateway/"
    }
    """
    now = time.time()
    cached = _token_cache["token_data"]
    cached_time = _token_cache["timestamp"]

    if cached and (now - cached_time) < _TOKEN_TTL:
        return cached

    url = "https://cloud.seatable.io/api/v2.1/dtable/app-access-token/"
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
            '0000': 'usertest01_seller',
            'Cv8Z': '+7981XXXXXXX',
            'XKVt': [{'display_value': 'sale', 'row_id': 'Mw_3fNzwRQinL7RLTFQN0Q'}],
            '_archived': False,
            '_creator': '5155027b66d445bb96ccf5a9f7452ce4@auth.local',
            '_ctime': '2025-07-08T13:58:08.914+02:00',
            '_id': 'HiQYOMv4SLSsSMF_EpGpOg',
            '_last_modifier': '5155027b66d445bb96ccf5a9f7452ce4@auth.local',
            '_locked': None,
            '_locked_by': None,
            '_mtime': '2025-07-14T15:59:10.958+02:00'
        },
    ]
    Пример словаря для mailboxes:
    [
        {
            '0000': 'sale',
            '8OBK': 'box01@mail.ru',
            '8sUx': [{'display_value': 'usertest01_seller',
            'row_id': 'HiQYOMv4SLSsSMF_EpGpOg'}],
            'XE9i': 'дашборды по продажам',
            '_archived': False,
            '_creator': '5155027b66d445bb96ccf5a9f7452ce4@auth.local',
            '_ctime': '2025-07-08T14:06:44.441+02:00',
            '_id': 'Mw_3fNzwRQinL7RLTFQN0Q',
            '_last_modifier': '5155027b66d445bb96ccf5a9f7452ce4@auth.local',
            '_locked': None,
            '_locked_by': None,
            '_mtime': '2025-07-14T16:03:12.951+02:00'
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

    url = f"{base_url}/api/v2/dtables/{dtable_uuid}/rows/"
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

    url = f"{base_url}/api/v2/dtables/{dtable_uuid}/columns/"
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


#

async def prepare_for_db() -> Dict[str, Any]:
    """
    Возвращает сокращенные словари, чтобы было удобно синхронизировать с Postgres
    {'mailboxes': [{'description': 'дашборды по продажам',
                'email': 'box1@mail.ru',
                'name': 'sale',
                'seatable_id': 'Mw_3fNzwRQinL7RLTFQN0Q'},
               {'description': 'для руководителей',
                'email': 'box2@mail.ru',
                'name': 'top',
                'seatable_id': 'Rp5djUppTcqM1LQO_3x_gg'}],
 'relations': [{'mailbox_seatable_id': 'Mw_3fNzwRQinL7RLTFQN0Q',
                'user_seatable_id': 'HiQYOMv4SLSsSMF_EpGpOg'},
               {'mailbox_seatable_id': 'Rp5djUppTcqM1LQO_3x_gg',
                'user_seatable_id': 'ZbyFNPKjTtCz6CWc7cbE5Q'}],
 'users': [{'last_uid': None,
            'name': 'usertest01_seller',
            'phone': '+7981XXXXXXX',
            'seatable_id': 'HiQYOMv4SLSsSMF_EpGpOg',
            'telegram_id': None},
           {'last_uid': None,
            'name': 'usertest02_head',
            'phone': '+7921XXXXXXX',
            'seatable_id': 'ZbyFNPKjTtCz6CWc7cbE5Q',
            'telegram_id': None}]}
    """
    # Получаем данные из таблиц
    users_data = await fetch_table(Config.SEATABLE_USERS_TABLE_ID)
    mailboxes_data = await fetch_table(Config.SEATABLE_MAILBOXES_TABLE_ID)

    # Получаем метаданные таблиц
    users_metadata = await get_table_columns(Config.SEATABLE_USERS_TABLE_ID)
    mailboxes_metadata = await get_table_columns(Config.SEATABLE_MAILBOXES_TABLE_ID)

    # Создаем словари для быстрого доступа к данным
    mailboxes_map = {mb['_id']: mb for mb in mailboxes_data}
    users_map = {user['_id']: user for user in users_data}

    # Определяем ключи колонок из метаданных
    def find_column_key(metadata, column_name):
        if not isinstance(metadata, dict) or 'columns' not in metadata:
            return None
        for col in metadata['columns']:
            if col.get('name') == column_name:
                return col.get('key')
        return None

    # Подготовка данных для пользователей
    users_to_db = []
    mailboxes_to_db = []
    user_mailbox_relations = []

    # Сначала обрабатываем почтовые ящики
    for mailbox in mailboxes_data:
        try:
            mailbox_dict = {
                'seatable_id': mailbox.get('_id', ''),
                'name': mailbox.get(find_column_key(mailboxes_metadata, 'Name') or '0000', ''),
                'email': mailbox.get(find_column_key(mailboxes_metadata, 'email') or '8OBK', ''),
                'description': mailbox.get(find_column_key(mailboxes_metadata, 'description') or 'XE9i', None)
            }
            mailboxes_to_db.append(mailbox_dict)
        except Exception as e:
            logger.error(f"Ошибка обработки почтового ящика {mailbox.get('_id')}: {str(e)}")
            continue

    # Затем обрабатываем пользователей и связи
    for user in users_data:
        try:
            user_dict = {
                'seatable_id': user.get('_id', ''),
                'name': user.get(find_column_key(users_metadata, 'Name') or '0000', ''),
                'phone': normalize_phone(user.get(find_column_key(users_metadata, 'phone') or 'Cv8Z', None)),
                'telegram_id': None,
                'last_uid': None
            }
            users_to_db.append(user_dict)

            # Обрабатываем связи пользователь-почтовый ящик
            mailboxes_key = find_column_key(users_metadata, 'mailboxes') or 'KqFx'
            if mailboxes_key in user:
                for mailbox_ref in user[mailboxes_key]:
                    if not isinstance(mailbox_ref, dict):
                        continue
                    mailbox_id = mailbox_ref.get('row_id')
                    if mailbox_id and mailbox_id in mailboxes_map:
                        user_mailbox_relations.append({
                            'user_seatable_id': user['_id'],
                            'mailbox_seatable_id': mailbox_id
                        })

        except Exception as e:
            logger.error(f"Ошибка обработки пользователя {user.get('_id')}: {str(e)}")
            continue

    return {
        'users': users_to_db,
        'mailboxes': mailboxes_to_db,
        'relations': user_mailbox_relations
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