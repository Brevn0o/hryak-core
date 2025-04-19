import json, string, random

from .connection import Connection
from ..functions import Func
from hryak import config

class PromoCode:

    @staticmethod
    async def exists(code: str):
        result = await Connection.make_request(
            f"SELECT EXISTS(SELECT 1 FROM {config.promocodes_schema} WHERE id = %s)",
            params=(code,),
            commit=False,
            fetch=True
        )
        return bool(result)

    @staticmethod
    async def create(max_uses: int, rewards: dict, lifespan: int = None, code: str = None):
        if code is None:
            code = ''.join([random.choice(string.ascii_letters +
                                          string.digits) for _ in range(12)])
        await Connection.make_request(
            f"INSERT INTO {config.promocodes_schema} (id, created, max_uses, users_used, prise, expires_in) "
            f"VALUES (%s, %s, %s, %s, %s, %s)",
            params=(code, Func.generate_current_timestamp(), max_uses, json.dumps([]), json.dumps(rewards), lifespan)
        )
        return code

    @staticmethod
    async def delete(code: str):
        await Connection.make_request(
            f"DELETE FROM {config.promocodes_schema} WHERE id = %s",
            params=(code,),
        )

    @staticmethod
    async def get_rewards(code: str):
        result = await Connection.make_request(
            f"SELECT prise FROM {config.promocodes_schema} WHERE id = %s",
            params=(code,),
            commit=False,
            fetch=True
        )
        print(type(result), result)
        return json.loads(result)

    @staticmethod
    async def used_times(code: str):
        users_used = await PromoCode.get_users_used(code)
        return len(users_used)

    @staticmethod
    async def get_user_used_times(code: str, user_id):
        users_used = await PromoCode.get_users_used(code)
        return users_used.count(str(user_id))

    @staticmethod
    async def max_uses(code: str):
        result = await Connection.make_request(
            f"SELECT max_uses FROM {config.promocodes_schema} WHERE id = '{code}'",
            commit=False,
            fetch=True
        )
        return result

    @staticmethod
    async def created(code: str):
        result = await Connection.make_request(
            f"SELECT created FROM {config.promocodes_schema} WHERE id = '{code}'",
            commit=False,
            fetch=True
        )
        return int(result)

    @staticmethod
    async def get_users_used(code: str) -> list:
        result = await Connection.make_request(
            f"SELECT users_used FROM {config.promocodes_schema} WHERE id = '{code}'",
            commit=False,
            fetch=True
        )
        if result is not None:
            return json.loads(result)
        else:
            return []

    @staticmethod
    async def expires_in(code: str):
        result = await Connection.make_request(
            f"SELECT expires_in FROM {config.promocodes_schema} WHERE id = '{code}'",
            commit=False,
            fetch=True
        )
        return result

    @staticmethod
    async def add_users_used(code: str, user_id):
        users_used = await PromoCode.get_users_used(code)
        users_used.append(str(user_id))
        await PromoCode.set_new_users_used(code, users_used)

    @staticmethod
    async def set_new_users_used(code: str, new_users: list):
        new_users = json.dumps(new_users, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.promocodes_schema} SET users_used = '{new_users}' WHERE id = '{code}'"
        )
