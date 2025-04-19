import json

import aiocache
from cachetools import cached

from .connection import Connection
from ..functions import Func
from hryak import config


class History:

    @staticmethod
    async def fix_history_structure_for_all_users(nested_key_path: str = '', standard_values: dict = None):
        if standard_values is None:
            standard_values = config.default_history
        await Connection.make_request(f"UPDATE {config.users_schema} SET history = '{'{}'}' WHERE history IS NULL")
        for k, v in standard_values.items():
            new_key_path = f"{nested_key_path}.{k}" if nested_key_path else k
            if type(v) in [dict]:
                await Connection.make_request(f"""
                UPDATE {config.users_schema}
                SET history = JSON_SET(history, '$.{new_key_path}', CAST(%s AS JSON))
                WHERE JSON_EXTRACT(history, '$.{new_key_path}') IS NULL;
                """, params=(json.dumps(v),))
                await History.fix_history_structure_for_all_users(new_key_path, standard_values[k])
            else:
                await Connection.make_request(f"""
                UPDATE {config.users_schema}
                SET history = JSON_SET(history, '$.{new_key_path}', {'CAST(%s AS JSON)' if isinstance(v, list) else '%s'})
                WHERE JSON_EXTRACT(history, '$.{new_key_path}') IS NULL;
                """, params=(json.dumps(v) if isinstance(v, list) else v,))

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="history.get")
    async def get(user_id: int) -> dict:
        result = await Connection.make_request(
            f"SELECT history FROM {config.users_schema} WHERE id = %s",
            params=(user_id,),
            commit=False,
            fetch=True,
        )
        if result is not None:
            return json.loads(result)
        else:
            return {}

    @staticmethod
    async def update_history(user_id: int, new_history: dict):
        new_history = json.dumps(new_history, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET history = %s WHERE id = %s", (new_history, user_id)
        )
        await History.clear_get_history_cache(user_id)

    @staticmethod
    async def clear_get_history_cache(user_id: int):
        await Func.clear_db_cache('history.get', History.get, (user_id,))

    @staticmethod
    async def get_feed_history(user_id: int):
        history = await History.get(user_id)
        return history[f'feed_history']

    @staticmethod
    async def add_feed_to_history(user_id: int, timestamp: int):
        history = await History.get(user_id)
        history[f'feed_history'].append(timestamp)
        await History.update_history(user_id, history)

    @staticmethod
    async def get_last_feed(user_id: int):
        history = await History.get(user_id)
        last_feed = None
        if len(history[f'feed_history']) > 0:
            last_feed = history[f'feed_history'][-1]
        return last_feed

    @staticmethod
    async def get_butcher_history(user_id: int):
        history = await History.get(user_id)
        return history[f'butcher_history']

    @staticmethod
    async def add_butcher_to_history(user_id: int, timestamp: int):
        history = await History.get(user_id)
        history[f'butcher_history'].append(timestamp)
        await History.update_history(user_id, history)

    @staticmethod
    async def get_last_butcher(user_id: int):
        history = await History.get(user_id)
        last_feed = None
        if len(history[f'butcher_history']) > 0:
            last_feed = history[f'butcher_history'][-1]
        return last_feed

    @staticmethod
    async def get_streak_history(user_id: int):
        history = await History.get(user_id)
        return history[f'streak_history']

    @staticmethod
    async def add_streak_to_history(user_id: int, timestamp: int, _type):
        history = await History.get(user_id)
        history[f'streak_history'].append({'timestamp': timestamp, 'type': _type})
        await History.update_history(user_id, history)

    @staticmethod
    async def get_last_streak_timestamp(user_id: int):
        history = await History.get_streak_history(user_id)
        res = -1
        if history:
            res = history[-1]['timestamp']
        return res

    @staticmethod
    async def get_shop_history(user_id: int):
        result = await Connection.make_request(
            f"SELECT history FROM {config.users_schema} WHERE id = %s",
            params=(user_id,),
            commit=False,
            fetch=True,
        )
        return json.loads(result)['shop_history']

    @staticmethod
    async def append_shop_history(user_id: int, item_id: str, amount: int):
        history = await History.get(user_id)
        history['shop_history'].append({item_id: Func.generate_current_timestamp(), 'amount': amount})
        await History.update_history(user_id, history)

