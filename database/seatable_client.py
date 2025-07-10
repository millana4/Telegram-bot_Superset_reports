import aiohttp
from typing import List, Dict, Optional
import logging
from config import Config

logger = logging.getLogger(__name__)

async def get_base_token() -> Optional[Dict]:
    """
    Получает временный токен для синхронизации по Апи.
    Возвращает словарь:
    {
        "app_name": "ssetuser",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJleHAiOjE3NTIzMjY4NTAsImR0YWJsZV91dWlkIjoiNGNhY2ZiMWEtN2Q2OS00NWVjLWIxODEtOTUyYjkxM2UxNDgzIiwicGVybWlzc2lvbiI6InIiLCJvcmdfaWQiOjYyMDMxLCJvd25lcl9pZCI6IjUxNTUwMjdiNjZkNDQ1YmI5NmNjZjVhOWY3NDUyY2U0QGF1dGgubG9jYWwiLCJhcHBfbmFtZSI6InNzZXR1c2VyIiwidXNlcm5hbWUiOiIiLCJpZF9pbl9vcmciOiIiLCJ1c2VyX2RlcGFydG1lbnRfaWRzX21hcCI6eyJjdXJyZW50X3VzZXJfZGVwYXJ0bWVudF9pZHMiOltdLCJjdXJyZW50X3VzZXJfZGVwYXJ0bWVudF9hbmRfc3ViX2lkcyI6W119fQ.2C1CdO6N9fFE61rV_03WsqoL-ADTUG5Je5kEN03tG2E",
        "dtable_uuid": "4cacfb1a-7d69-45ec-b181-952b913e1483",
        "workspace_id": 82533,
        "dtable_name": "users_sset-grp",
        "use_api_gateway": true,
        "dtable_server": "https://cloud.seatable.io/api-gateway/"
    }
    """
    url = "https://cloud.seatable.io/api/v2.1/dtable/app-access-token/"
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {Config.SEATABLE_API_TOKEN}"
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()  # Вызовет исключение для 4XX/5XX статусов
                token_data = await response.json()
                logger.debug("Base token successfully obtained")
                return token_data

    except aiohttp.ClientError as e:
        logger.error(f"API request failed: {str(e)}")
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")

    return None


async def fetch_tables(tablename) -> List[Dict]:
    """
    Запрашивает таблицу пользователей из SeaTable с автоматическим получением токена

    Первый вызов — возвращает словарь с данными пользователей, которые получил из таблицы Seatable Table1 с полями Name-Tel-Grp:
    {'rows':
        [
            {
                '0000': 'usertest01',
                'Cv8Z': '+7981XXXXXXX',
                'XKVt':
                    [
                        {'row_id': 'Mw_3fNzwRQinL7RLTFQN0Q', 'display_value': '1'}
                    ],
                '_locked': None,
                '_locked_by': None,
                '_archived': False,
                '_creator': '5155027b66d445bb96ccf5a9f7452ce4@auth.local',
                '_ctime': '2025-07-08T13:58:08.914+02:00',
                '_last_modifier': '5155027b66d445bb96ccf5a9f7452ce4@auth.local',
                '_mtime': '2025-07-08T15:13:04.366+02:00',
                '_id': 'HiQYOMv4SLSsSMF_EpGpOg'
            },
            {
                '0000': 'usertest02',
                'Cv8Z': '+7921XXXXXXX',
                'XKVt':
                    [
                        {'row_id': 'Rp5djUppTcqM1LQO_3x_gg', 'display_value': '2'}
                    ],
                '_locked': None,
                '_locked_by': None,
                '_archived': False,
                '_creator': '5155027b66d445bb96ccf5a9f7452ce4@auth.local',
                '_ctime': '2025-07-08T13:58:08.914+02:00',
                '_last_modifier': '5155027b66d445bb96ccf5a9f7452ce4@auth.local',
                '_mtime': '2025-07-08T15:13:08.706+02:00',
                '_id': 'ZbyFNPKjTtCz6CWc7cbE5Q'},
        ]
    }

    Второй вызов — возвращает словарь с имейлами пользователей, которые получил из таблицы Seatable grp с полями Name-Email-Grp-Table1:
    {'rows':
        [
            {
                '0000': '1',
                '8OBK': 'sr01@r2d.ru',
                'J0jc': ['277964', '637609'],
                '8sUx': [{'row_id': 'HiQYOMv4SLSsSMF_EpGpOg', 'display_value': 'usertest01'}],
                '_locked': None,
                '_locked_by': None,
                '_archived': False,
                '_creator': '5155027b66d445bb96ccf5a9f7452ce4@auth.local',
                '_ctime': '2025-07-08T14:06:44.441+02:00',
                '_last_modifier': '5155027b66d445bb96ccf5a9f7452ce4@auth.local',
                '_mtime': '2025-07-08T15:15:40.052+02:00',
                '_id': 'Mw_3fNzwRQinL7RLTFQN0Q'}
            }
        ]
    }
    """

    # Сначала получаем базовый токен
    token_data = await get_base_token()
    if not token_data:
        logger.error("Failed to obtain base token")
        return []

    # Формируем запрос с полученным токеном
    url = (f"https://cloud.seatable.io/api-gateway/api/v2/dtables/{token_data['dtable_uuid']}/rows/")
    headers = {
        "accept": "application/json",
        "authorization": f"Bearer {token_data['access_token']}"
    }
    params = {"table_name": tablename}  # название таблицы — Table1 или grp

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, params=params) as response:
                if response.status != 200:
                    error = await response.text()
                    logger.error(f"API request failed in def fetch_users() с Table1: {response.status} - {error}")
                    return []

                data = await response.json()
                print(data)
                return data

    except Exception as e:
        logger.error(f"Request error: {str(e)}")
        return []