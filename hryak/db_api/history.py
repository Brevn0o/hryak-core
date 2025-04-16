import json

from .connection import Connection
from ..functions import Func
from hryak import config


class History:

    @staticmethod
    def fix_history_structure_for_all_users(nested_key_path: str = '', standard_values: dict = None):
        if standard_values is None:
            standard_values = config.default_history
        Connection.make_request(f"UPDATE {config.users_schema} SET history = '{'{}'}' WHERE history IS NULL")
        for k, v in standard_values.items():
            new_key_path = f"{nested_key_path}.{k}" if nested_key_path else k
            if type(v) in [dict]:
                Connection.make_request(f"""
                UPDATE {config.users_schema}
                SET history = JSON_SET(history, '$.{new_key_path}', CAST(%s AS JSON))
                WHERE JSON_EXTRACT(history, '$.{new_key_path}') IS NULL;
                """, params=(json.dumps(v),))
                History.fix_history_structure_for_all_users(new_key_path, standard_values[k])
            else:
                Connection.make_request(f"""
                UPDATE {config.users_schema}
                SET history = JSON_SET(history, '$.{new_key_path}', {'CAST(%s AS JSON)' if isinstance(v, list) else '%s'})
                WHERE JSON_EXTRACT(history, '$.{new_key_path}') IS NULL;
                """, params=(json.dumps(v) if isinstance(v, list) else v,))

    @staticmethod
    def get(user_id) -> dict:
        if type(user_id) is not list:
            result = Connection.make_request(
                f"SELECT history FROM {config.users_schema} WHERE id = %s",
                params=(user_id,),
                commit=False,
                fetch=True,
            )
            if result is not None:
                return json.loads(result)
            else:
                return {}
        else:
            user_ids = []
            for i in user_id:
                user_ids.append(int(i))
            result = Connection.make_request(
                f"SELECT history FROM {config.users_schema} WHERE id IN %s",
                params=(tuple(user_ids)),
                commit=False,
                fetch=True,
                fetchall=True,
                fetch_first=False
            )
            if result is not None:
                final_result = {}
                for i, j in enumerate(result):
                    final_result[user_ids[i]] = json.loads(j[0])
                return final_result
            else:
                return {}

    @staticmethod
    def update_history(user_id: int, new_history):
        new_history = json.dumps(new_history, ensure_ascii=False)
        Connection.make_request(
            f"UPDATE {config.users_schema} SET history = %s WHERE id = %s", (new_history, user_id)
        )

    @staticmethod
    def get_feed_history(user_id: int):
        history = History.get(user_id)
        return history[f'feed_history']

    @staticmethod
    def add_feed_to_history(user_id: int, timestamp: int):
        history = History.get(user_id)
        history[f'feed_history'].append(timestamp)
        History.update_history(user_id, history)

    @staticmethod
    def get_last_feed(user_id: int):
        history = History.get(user_id)
        last_feed = None
        if len(history[f'feed_history']) > 0:
            last_feed = history[f'feed_history'][-1]
        return last_feed

    @staticmethod
    def get_butcher_history(user_id: int):
        history = History.get(user_id)
        return history[f'butcher_history']

    @staticmethod
    def add_butcher_to_history(user_id: int, timestamp: int):
        history = History.get(user_id)
        history[f'butcher_history'].append(timestamp)
        History.update_history(user_id, history)

    @staticmethod
    def get_last_butcher(user_id: int):
        history = History.get(user_id)
        last_feed = None
        if len(history[f'butcher_history']) > 0:
            last_feed = history[f'butcher_history'][-1]
        return last_feed

    @staticmethod
    def get_streak_history(user_id: int):
        history = History.get(user_id)
        return history[f'streak_history']

    @staticmethod
    def add_streak_to_history(user_id: int, timestamp: int, _type):
        history = History.get(user_id)
        history[f'streak_history'].append({'timestamp': timestamp, 'type': _type})
        History.update_history(user_id, history)

    @staticmethod
    def get_last_streak_timestamp(user_id: int):
        history = History.get_streak_history(user_id)
        res = -1
        if history:
            res = history[-1]['timestamp']
        return res

    @staticmethod
    def get_shop_history(user_id: int):
        result = Connection.make_request(
            f"SELECT history FROM {config.users_schema} WHERE id = %s",
            params=(user_id,),
            commit=False,
            fetch=True,
        )
        return json.loads(result)['shop_history']

    @staticmethod
    def append_shop_history(user_id: int, item_id: str, amount: int):
        history = History.get(user_id)
        history['shop_history'].append({item_id: Func.generate_current_timestamp(), 'amount': amount})
        History.update_history(user_id, history)

