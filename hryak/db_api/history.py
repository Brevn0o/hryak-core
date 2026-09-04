import json

import aiocache
from cachetools import cached

from .connection import Connection
from .schema import user_id_column
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
    # @aiocache.cached(key_builder=Func.cache_key_builder, alias="history.get")
    async def get(user_id: int) -> dict:
        result = await Connection.make_request(
            f"SELECT history FROM {config.users_schema} WHERE {user_id_column()} = %s",
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
            f"UPDATE {config.users_schema} SET history = %s WHERE {user_id_column()} = %s", (new_history, user_id)
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
    async def get_server_feed_history(user_id: int):
        history = await History.get(user_id)
        return history[f'server_feed_history']

    @staticmethod
    def server_feed_timestamp(entry):
        """When a server feed happened, whichever shape the entry is written in.

        Entries were a bare timestamp before the guild was recorded next to them. Both
        have to read: an account whose last feed predates the change must still have its
        cooldown counted, rather than reading as somebody who has never fed at all.
        """
        return entry.get('timestamp') if isinstance(entry, dict) else entry

    @staticmethod
    async def add_server_feed_to_history(user_id: int, timestamp: int, guild_id=None):
        """Records a community feed, and which pig it was.

        The guild is kept as a string - discord ids run past what json numbers hold
        exactly, and one written as a number comes back rounded.
        """
        history = await History.get(user_id)
        history['server_feed_history'].append(
            {'timestamp': timestamp, 'guild_id': str(guild_id)} if guild_id is not None
            else timestamp)
        await History.update_history(user_id, history)

    @staticmethod
    async def get_last_server_feed(user_id: int):
        history = await History.get(user_id)
        entries = history['server_feed_history']
        return History.server_feed_timestamp(entries[-1]) if entries else None

    @staticmethod
    async def get_last_server_fed_guild(user_id: int):
        """The last community pig this person fed, or None if that was never recorded.

        Walks back rather than reading the last entry alone, so somebody whose most recent
        feed predates the guild being stored still gets the one before it that does.
        """
        history = await History.get(user_id)
        for entry in reversed(history['server_feed_history']):
            if isinstance(entry, dict) and entry.get('guild_id'):
                return entry['guild_id']
        return None

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
            f"SELECT history FROM {config.users_schema} WHERE {user_id_column()} = %s",
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

