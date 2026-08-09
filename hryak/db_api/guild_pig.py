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
    # @aiocache.cached(key_builder=Func.cache_key_builder, alias="guild_pig.get")
    async def get_raw(guild_id) -> dict:
        """Whatever is actually stored in the column, nothing filled in."""
        result = await Connection.make_request(
            f"SELECT pig FROM {config.guilds_schema} WHERE id = %s",
            params=(guild_id,),
            commit=False,
            fetch=True,
        )
        if result is not None:
            return json.loads(result)
        else:
            return {}

    @staticmethod
    async def get(guild_id) -> dict:
        """Always returns a whole pig, even for a guild that has never set one up.

        The column is null until the guild is registered or the structure fix runs, and
        a guild the bot has just joined would otherwise KeyError on every getter - and,
        worse, let a setter write a pig with only the one key it touched.

        The defaults are filled in outside the cache on purpose: a key added to
        default_guild_pig then reaches pigs that are already cached, instead of waiting
        out a shared redis entry.
        """
        return {**copy.deepcopy(config.default_guild_pig), **await GuildPig.get_raw(guild_id)}

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
        await Func.clear_db_cache('guild_pig.get', GuildPig.get_raw, guild_id)

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
        pig['skins'] = await Pig.set_skin_to_options(pig['skins'], item_id, layer, context='server')
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def remove_skin(guild_id, item_id, layer=None):
        from .pig import Pig
        pig = await GuildPig.get(guild_id)
        pig['skins'] = await Pig.remove_skin_from_options(pig['skins'], item_id, layer, context='server')
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_skin(guild_id, key):
        pig = await GuildPig.get(guild_id)
        if key == 'all':
            return pig['skins']
        if key in pig['skins']:
            return pig['skins'][key]

    @staticmethod
    async def is_skin_worn(guild_id, item_id):
        """Whether the pig has this on right now.

        Eyes, pupils and body sit on several layers at once and any one of them counts as
        worn, which is the same rule the personal wardrobe draws its buttons by.
        """
        skins = await GuildPig.get_skin(guild_id, 'all')
        skin_type = await Item.get_skin_type(item_id, context='server')
        if skin_type in ['eyes', 'pupils', 'body']:
            return any(skins.get(layer) == item_id
                       for layer in await Item.get_skin_layers(item_id, 'server'))
        return skin_type is not None and skins.get(skin_type) == item_id

    @staticmethod
    async def get_inventory(guild_id):
        pig = await GuildPig.get(guild_id)
        return pig['inventory']

    @staticmethod
    async def set_new_inventory(guild_id, new_inventory):
        pig = await GuildPig.get(guild_id)
        pig['inventory'] = new_inventory
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def add_item(guild_id, item_id, amount: int = 1):
        from .user import User
        inventory = await GuildPig.get_inventory(guild_id)
        await GuildPig.set_new_inventory(guild_id, User.add_item_to_inventory(inventory, item_id, amount))

    @staticmethod
    async def remove_item(guild_id, item_id, amount: int = 1):
        await GuildPig.add_item(guild_id, item_id, -amount)


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
    async def set_channel(guild_id, channel_id, created_by_bot: bool = False, key: str = 'channel'):
        """key picks which home is being set - 'channel' for the pig, 'poll_channel' for
        votes, 'notification_channel' for announcements, 'admin_channel' for the panel."""
        pig = await GuildPig.get(guild_id)
        pig[f'{key}_id'] = channel_id
        pig[f'{key}_created_by_bot'] = created_by_bot
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_channel(guild_id, key: str = 'channel'):
        pig = await GuildPig.get(guild_id)
        return pig[f'{key}_id']

    @staticmethod
    async def is_channel_created_by_bot(guild_id, key: str = 'channel'):
        pig = await GuildPig.get(guild_id)
        return pig[f'{key}_created_by_bot']

    @staticmethod
    async def set_message(guild_id, message_id, key: str = 'message'):
        """key picks which of hryak's own messages is meant - 'message' for the pig itself,
        'admin_message' for the panel only staff can see."""
        pig = await GuildPig.get(guild_id)
        pig[f'{key}_id'] = message_id
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_message(guild_id, key: str = 'message'):
        pig = await GuildPig.get(guild_id)
        return pig[f'{key}_id']

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
    async def get_feeders(guild_id, since: int = None):
        """Who has fed this pig, optionally only since a moment - the server's active
        members, which is what a vote is measured against."""
        return {str(feed['user_id']) for feed in await GuildPig.get_feeds(guild_id, since)}

    @staticmethod
    async def get_poll(guild_id, kind: str):
        pig = await GuildPig.get(guild_id)
        return (pig['polls'] or {}).get(kind)

    @staticmethod
    async def set_poll(guild_id, kind: str, poll: dict = None):
        """Pass no poll to clear the slot once the vote is done."""
        pig = await GuildPig.get(guild_id)
        polls = dict(pig['polls'] or {})
        if poll is None:
            polls.pop(kind, None)
        else:
            polls[kind] = poll
        pig['polls'] = polls
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_last_proposal(guild_id, user_id):
        pig = await GuildPig.get(guild_id)
        return (pig['proposals'] or {}).get(str(user_id)) or 0

    @staticmethod
    async def set_last_proposal(guild_id, user_id, timestamp: int):
        pig = await GuildPig.get(guild_id)
        proposals = dict(pig['proposals'] or {})
        proposals[str(user_id)] = timestamp
        pig['proposals'] = proposals
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_polls_allowed(guild_id):
        """Whether members may open votes to buy and to dress the pig."""
        pig = await GuildPig.get(guild_id)
        return pig['polls_allowed']

    @staticmethod
    async def set_polls_allowed(guild_id, allowed: bool):
        pig = await GuildPig.get(guild_id)
        pig['polls_allowed'] = bool(allowed)
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_last_payout(guild_id):
        pig = await GuildPig.get(guild_id)
        return pig['last_payout']

    @staticmethod
    async def set_last_payout(guild_id, timestamp: int):
        pig = await GuildPig.get(guild_id)
        pig['last_payout'] = timestamp
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_paid_until(guild_id, user_id=None):
        """When each person was last paid. Feeds after that mark are what they are owed for.

        Nothing is ever removed from the feed list - this is what says which part of it has
        already been settled, and it is kept per person on purpose: somebody who fed too
        little to be paid keeps their mark where it was, so what they fed still counts next
        time instead of being lost to a window that has moved on without them.
        """
        pig = await GuildPig.get(guild_id)
        marks = pig['paid_until'] or {}
        if user_id is None:
            return marks
        return marks.get(str(user_id)) or 0

    @staticmethod
    async def set_paid_until(guild_id, marks: dict):
        """Moves the mark forward for the people who were actually paid, and only them.

        Each mark is that person's last feed the payout actually counted, not the moment the
        payout ran - a feed landing in the same second as the payout would otherwise be
        marked as settled without ever having been paid for.
        """
        pig = await GuildPig.get(guild_id)
        new_marks = dict(pig['paid_until'] or {})
        for user_id, timestamp in marks.items():
            new_marks[str(user_id)] = timestamp
        pig['paid_until'] = new_marks
        await GuildPig.update_pig(guild_id, pig)

    @staticmethod
    async def get_all_setup_guild_ids_for_payout():
        """Every guild with a pig that has been fed, so the weekly run walks a short list."""
        result = await Connection.make_request(
            f"SELECT id FROM {config.guilds_schema} "
            f"WHERE JSON_LENGTH(JSON_EXTRACT(pig, '$.feeds')) > 0",
            commit=False, fetch=True, fetchall=True)
        if result is None:
            return []
        return [i[0] for i in result]

    @staticmethod
    async def get_all_guilds_with_polls():
        """Only the guilds with something open, so the finaliser walks a short list."""
        result = await Connection.make_request(
            f"SELECT id FROM {config.guilds_schema} "
            f"WHERE JSON_LENGTH(JSON_EXTRACT(pig, '$.polls')) > 0",
            commit=False, fetch=True, fetchall=True)
        if result is None:
            return []
        return [i[0] for i in result]

    @staticmethod
    async def get_last_feed(guild_id, user_id=None):
        """When the pig was last fed - by anyone, or by one user if user_id is given."""
        feeds = await GuildPig.get_feeds(guild_id, user_id=user_id)
        if feeds:
            return max(feed['timestamp'] for feed in feeds)
