import asyncio, json

import aiocache

from .connection import Connection
from .tech import Tech
from ..functions import Func
from hryak import config



class Guild:

    @staticmethod
    async def register_guild_if_not_exists(guild_id):
        if not await Guild.exists(guild_id):
            await Guild.register(guild_id)

    @staticmethod
    async def register(guild_id):
        if type(guild_id) in [list, tuple]:
            guild_ids = [(guild, Func.generate_current_timestamp(), json.dumps(config.guild_settings)) for guild in
                         guild_id]
            query = f"INSERT IGNORE INTO {config.guilds_schema} (id, joined, settings) VALUES (%s, %s, %s)"
            await Connection.make_request(query, params=tuple(guild_ids), executemany=True)
        else:
            query = f"INSERT INTO {config.guilds_schema} (id, joined, settings) VALUES (%s, %s, %s)"
            await Connection.make_request(query, params=(
            guild_id, Func.generate_current_timestamp(), json.dumps(config.guild_settings)),
                                    executemany=False)

    @staticmethod
    async def exists(guild_id):
        result = await Connection.make_request(
            f"SELECT EXISTS(SELECT 1 FROM {config.guilds_schema} WHERE id = {guild_id})",
            commit=False,
            fetch=True
        )
        return bool(result)

    @staticmethod
    async def fix_settings_structure_for_all_guilds():
        guilds = await Tech.get_all_guilds()
        for guild in guilds:
            await Guild.fix_settings_structure(guild)
            await asyncio.sleep(.1)

    @staticmethod
    async def fix_settings_structure(guild_id):
        settings = await Guild.get_settings(guild_id)
        if settings is None:
            settings = {}
        for key, value in config.guild_settings.items():
            if key not in settings:
                settings[key] = value
        await Guild.set_settings(guild_id, settings)

    @staticmethod
    @aiocache.cached(key="user.get_settings:{user_id}", alias="user.get_settings")
    async def get_settings(guild_id):
        result = await Connection.make_request(
            f"SELECT settings FROM {config.guilds_schema} WHERE id = %s",
            params=(guild_id,),
            commit=False,
            fetch=True,
        )
        if result is not None:
            return json.loads(result)
        else:
            return {}

    @staticmethod
    async def set_settings(guild_id, new_settings):
        new_settings = json.dumps(new_settings, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.guilds_schema} SET settings = %s WHERE id = {guild_id}", (new_settings,)
        )

    @staticmethod
    async def set_join_channel(guild_id, channel_id):
        settings = await Guild.get_settings(guild_id)
        settings['join_channel'] = channel_id
        await Guild.set_settings(guild_id, settings)

    @staticmethod
    async def join_channel(guild_id):
        settings = await Guild.get_settings(guild_id)
        return settings['join_channel']

    @staticmethod
    async def set_join_message(guild_id, message):
        settings = await Guild.get_settings(guild_id)
        settings['join_message'] = message
        await Guild.set_settings(guild_id, settings)

    @staticmethod
    async def join_message(guild_id):
        settings = await Guild.get_settings(guild_id)
        return settings['join_message']

    @staticmethod
    async def is_say_allowed(guild_id):
        settings = await Guild.get_settings(guild_id)
        return settings['allow_say']

    @staticmethod
    async def allow_say(guild_id, allow: bool = True):
        settings = await Guild.get_settings(guild_id)
        settings['allow_say'] = allow
        await Guild.set_settings(guild_id, settings)

    @staticmethod
    # @cached(TTLCache(maxsize=utils_config.db_api_cash_size, ttl=utils_config.db_api_cash_ttl))
    async def joined(guild_id):
        result = await Connection.make_request(
            f"SELECT joined FROM {config.guilds_schema} WHERE id = %s",
            params=(guild_id,),
            commit=False,
            fetch=True,
        )
        if result is not None:
            return json.loads(result)
        else:
            return {}
