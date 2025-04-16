import asyncio
import os

from cachetools import cached

from .connection import Connection
from hryak import config
from .user import User
from .item import Item


class Tech:


    @staticmethod
    def get_all_users(extra_select: str, order_by: str = None, where: str = None, limit: int = None, guild = None):
        """
        :type extra_select: object
            Example: JSON_EXTRACT(inventory, '$.coins.amount')
        :type order_by: object
            Example: JSON_EXTRACT(inventory, '$.coins.amount')
        :param where:
            Example: JSON_EXTRACT(inventory, '$.coins.amount') > 0
        """
        id_list = []
        connection = Connection.connect()
        query = f'SELECT id, {extra_select} FROM {config.users_schema}'
        if where is not None:
            query += f" WHERE {where}"
        if order_by is not None:
            query += f" ORDER BY {order_by} DESC"
        if limit is not None and guild is None:
            query += f" LIMIT {limit}"
        with connection.cursor() as cursor:
            cursor.execute(query)
            results = cursor.fetchall()
            for i in results:
                id_list.append(i[0])
        if guild is not None:
            members_ids = [str(m.id) for m in guild.members]
            id_list = [i for i in id_list if i in members_ids]
            if limit is not None:
                id_list = id_list[:limit]
        return id_list

    @staticmethod
    def get_user_position(user_id, order_by: str = None, where: str = None, guild=None):
        users = Tech.get_all_users(order_by=order_by, where=where, guild=guild)
        if str(user_id) in users:
            return users.index(str(user_id))

    @staticmethod
    def get_all_guilds():
        id_list = []
        connection = Connection.connect()
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT id FROM {config.guilds_schema}")
            results = cursor.fetchall()
            for i in results:
                id_list.append(i[0])
        return id_list

    @staticmethod
    @cached(config.db_caches['tech.__get_all_items'])
    def __get_all_items(requirements: tuple = None, exceptions: tuple = None):
        result = []
        requirements = () if requirements is None else requirements
        exceptions = () if exceptions is None else exceptions
        for k, v in config.items.items():
            correct_item = True
            for i in exceptions:
                vv = v
                for j in range(len(i) - 1):
                    if vv is not None and i[j] in vv:
                        vv = vv[i[j]]
                if vv is not None and vv == i[-1]:
                    correct_item = False
                    break
            if correct_item:
                for i in requirements:
                    vv = v
                    for j in range(len(i) - 1):
                        if vv is not None and i[j] in vv:
                            vv = vv[i[j]]
                    if vv != i[-1]:
                        correct_item = False
                        break
            if correct_item:
                result.append(k)

        return result

    @staticmethod
    def clear_get___all_items_cache(params):
        try:
            config.db_caches['tech.__get_all_items'].pop(params)
        except KeyError:
            pass

    @staticmethod
    # @cached(utils_config.db_caches['tech.get_all_items'])
    def get_all_items(requirements: tuple = None, exceptions: tuple = None, user_id=None):
        """
        :type requirements: object
            Example: (("rarity", "3"),) - it will return only items with rarity=3
        :param exceptions:
            Example: (("type", "skin"),) - it will return everything except items with type=skin
        :param user_id:
            If user_id is specified, it will return items that are present in the user's inventory
        """
        result = Tech.__get_all_items(requirements, exceptions)
        if user_id is not None:
            result = [i for i in result if Item.get_amount(i, user_id) != 0]
            Tech.clear_get_all_items_cache((requirements, exceptions, user_id))
        return result

    @staticmethod
    def clear_get_all_items_cache(params):
        try:
            config.db_caches['tech.get_all_items'].pop(params)
        except KeyError:
            pass

    @staticmethod
    async def fix_settings_structure_for_all_users():
        users = Tech.get_all_users()
        for user in users:
            Tech.fix_settings_structure(user)
            await asyncio.sleep(0.1)

    @staticmethod
    def fix_settings_structure(user_id):
        settings = User.get_settings(user_id)
        if settings is None:
            settings = {}
        for key, value in config.user_settings.items():
            if key not in settings:
                settings[key] = value
        User.set_new_settings(user_id, settings)
