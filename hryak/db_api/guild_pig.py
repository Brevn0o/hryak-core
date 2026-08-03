import copy
import json

import aiocache

from .connection import Connection
from ..functions import Func, translate
from ..locale import Locale
from hryak import config
from .item import Item


class GuildPig:

    @staticmethod
    async def fix_pig_structure_for_all_guilds(nested_key_path: str = '', standard_values: dict = None):
        if standard_values is None:
            standard_values = config.default_guild_pig
        await Connection.make_request(f"UPDATE {config.guilds_schema} SET pig = %s WHERE pig IS NULL",
                                params=(json.dumps({}),))
        for k, v in standard_values.items():
            new_key_path = f"{nested_key_path}.{k}" if nested_key_path else k
            if type(v) in [dict]:
                await Connection.make_request(f"""
                UPDATE {config.guilds_schema}
                SET pig = JSON_SET(pig, '$.{new_key_path}', CAST(%s AS JSON))
                WHERE JSON_EXTRACT(pig, '$.{new_key_path}') IS NULL;
                """, params=(json.dumps(v),))
                await GuildPig.fix_pig_structure_for_all_guilds(new_key_path, standard_values[k])
            else:
                await Connection.make_request(f"""
                UPDATE {config.guilds_schema}
                SET pig = JSON_SET(pig, '$.{new_key_path}', {'CAST(%s AS JSON)' if isinstance(v, list) else '%s'})
                WHERE JSON_EXTRACT(pig, '$.{new_key_path}') IS NULL;
                """, params=(json.dumps(v) if isinstance(v, list) else v,))

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="guild_pig.get")
    async def get(guild_id) -> dict:
        """Always returns a whole pig, even for a guild that has never set one up.

        The column is null until the guild is registered or the structure fix runs, and
        a guild the bot has just joined would otherwise KeyError on every getter - and,
        worse, let a setter write a pig with only the one key it touched.
        """
        result = await Connection.make_request(
            f"SELECT pig FROM {config.guilds_schema} WHERE id = %s",
            params=(guild_id,),
            commit=False,
            fetch=True,
        )
        pig = json.loads(result) if result is not None else {}
        return {**copy.deepcopy(config.default_guild_pig), **pig}

    @staticmethod
    async def get_all_setup_guilds():
        """Ids of the guilds that gave the pig a home, so a restart only has to walk those
        and not every guild the bot is in. A json null reads as NOT NULL, hence JSON_TYPE."""
        result = await Connection.make_request(
            f"SELECT id FROM {config.guilds_schema} "
            f"WHERE JSON_TYPE(JSON_EXTRACT(pig, '$.channel_id')) NOT IN ('NULL')",
            commit=False,
            fetch=True,
            fetchall=True,
        )
        if result is None:
            return []
        return [i[0] for i in result]

    @staticmethod
    async def is_setup(guild_id):
        """Whether the guild has given the pig somewhere to live."""
        return await GuildPig.get_channel(guild_id) is not None

    @staticmethod
    async def clear_get_pig_cache(guild_id: int):
        await Func.clear_db_cache('guild_pig.get', GuildPig.get, guild_id)

    @staticmethod
    async def update_pig(guild_id: int, new_pig: dict):
        new_pig = json.dumps(new_pig, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.guilds_schema} SET pig = %s WHERE id = %s", (new_pig, guild_id)
        )
        await GuildPig.clear_get_pig_cache(guild_id)

    @staticmethod
    async def rename(guild_id, name: str):
        pig = await GuildPig.get(guild_id)
        pig['name'] = name
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_name(guild_id):
        pig = await GuildPig.get(guild_id)
        return pig['name']

    @staticmethod
    async def set_genetic(guild_id, key, value):
        pig = await GuildPig.get(guild_id)
        pig['genetic'][key] = value
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_genetic(guild_id, key):
        pig = await GuildPig.get(guild_id)
        if key == 'all':
            return pig['genetic']
        if key in pig['genetic']:
            return pig['genetic'][key]

    @staticmethod
    async def set_skin(guild_id, item_id, layer=None):
        from .pig import Pig
        pig = await GuildPig.get(guild_id)
        pig['skins'] = await Pig.set_skin_to_options(pig['skins'], item_id, layer)
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def remove_skin(guild_id, item_id, layer=None):
        from .pig import Pig
        pig = await GuildPig.get(guild_id)
        pig['skins'] = await Pig.remove_skin_from_options(pig['skins'], item_id, layer)
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_skin(guild_id, key):
        pig = await GuildPig.get(guild_id)
        if key == 'all':
            return pig['skins']
        if key in pig['skins']:
            return pig['skins'][key]

    @staticmethod
    async def add_weight(guild_id, weight: float):
        pig = await GuildPig.get(guild_id)
        pig['weight'] += weight
        pig['weight'] = round(pig['weight'], 1)
        if pig['weight'] <= .1:
            pig['weight'] = .1
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_weight(guild_id):
        pig = await GuildPig.get(guild_id)
        return pig['weight']

    @staticmethod
    async def set_channel(guild_id, channel_id, created_by_bot: bool = False):
        pig = await GuildPig.get(guild_id)
        pig['channel_id'] = channel_id
        pig['channel_created_by_bot'] = created_by_bot
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_channel(guild_id):
        pig = await GuildPig.get(guild_id)
        return pig['channel_id']

    @staticmethod
    async def is_channel_created_by_bot(guild_id):
        pig = await GuildPig.get(guild_id)
        return pig['channel_created_by_bot']

    @staticmethod
    async def set_message(guild_id, message_id):
        pig = await GuildPig.get(guild_id)
        pig['message_id'] = message_id
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_message(guild_id):
        pig = await GuildPig.get(guild_id)
        return pig['message_id']

    @staticmethod
    async def add_feed(guild_id, user_id, weight_added: float):
        """Records a feed and grows the pig by the same amount, so the two can't drift apart."""
        pig = await GuildPig.get(guild_id)
        pig['feeds'].append({'user_id': str(user_id),
                             'timestamp': Func.generate_current_timestamp(),
                             'weight_added': weight_added})
        pig['weight'] = round(pig['weight'] + weight_added, 1)
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_feeds(guild_id, since: int = None, user_id=None):
        """Every feed, newest last. `since` is a timestamp, for the weekly payout."""
        pig = await GuildPig.get(guild_id)
        feeds = pig['feeds']
        if since is not None:
            feeds = [feed for feed in feeds if feed['timestamp'] >= since]
        if user_id is not None:
            feeds = [feed for feed in feeds if str(feed['user_id']) == str(user_id)]
        return feeds

    @staticmethod
    async def get_weight_fed(guild_id, since: int = None, user_id=None):
        return round(sum(feed['weight_added'] for feed in await GuildPig.get_feeds(guild_id, since, user_id)), 1)

    @staticmethod
    async def get_last_feed(guild_id, user_id=None):
        """When the pig was last fed - by anyone, or by one user if user_id is given."""
        feeds = await GuildPig.get_feeds(guild_id, user_id=user_id)
        if feeds:
            return max(feed['timestamp'] for feed in feeds)
