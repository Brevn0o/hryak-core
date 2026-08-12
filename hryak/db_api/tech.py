import asyncio
import os

import aiocache
from cachetools import cached

from .connection import Connection
from .schema import user_id_column
from ..functions import Func
from hryak import config
from .user import User
from .item import Item
from .pig import Pig


class Tech:


    @staticmethod
    async def get_all_users(extra_select: str = None, order_by: str = None, where: str = None, limit: int = None, guild = None):
        """
        :type extra_select: object
            Example: JSON_EXTRACT(inventory, '$.coins.amount')
        :type order_by: object
            Example: JSON_EXTRACT(inventory, '$.coins.amount')
        :param where:
            Example: JSON_EXTRACT(inventory, '$.coins.amount') > 0
        """
        query = f'SELECT {user_id_column()}{f" , {extra_select}" if extra_select else ""} FROM {config.users_schema}'
        if where is not None:
            query += f" WHERE {where}"
        if order_by is not None:
            query += f" ORDER BY {order_by}"
        if limit is not None and guild is None:
            query += f" LIMIT {limit}"
        res = await Connection.make_request(query, commit=False, fetch=True, fetchall=True)
        if res is None:
            return []
        if guild is not None:
            members_ids = [str(m.id) for m in guild.members]
            res = [i for i in res if i[0] in members_ids]
            if limit is not None:
                res = res[:limit]
        if extra_select is None:
            res = [i[0] for i in res]
        return res

    @staticmethod
    async def get_users_to_remind(kind: str = 'feed_reminder'):
        """Ids of everyone who asked for this reminder and is owed one right now.

        The opted-in-and-not-yet-told part is asked of the database rather than walked in
        python - the users table is the whole userbase, and all but a handful of rows are
        ruled out by those two flags alone. Readiness is the only thing checked per person,
        since a cooldown cannot be expressed against the columns.
        """
        async def ready_to_butcher(user_id):
            # a knife is needed to butcher at all, so without one the reminder would only
            # be telling somebody to do something the bot would then refuse
            return (await Pig.is_ready_to_butcher(user_id)
                    and await Item.get_amount('knife', user_id) > 0)

        readiness = {'feed_reminder': Pig.is_ready_to_feed,
                     'butcher_reminder': ready_to_butcher}
        if kind not in readiness:
            return []
        candidates = await Tech.get_all_users(
            where=f"JSON_EXTRACT(settings, '$.notifications.{kind}') = CAST('true' AS JSON) "
                  f"AND (JSON_EXTRACT(stats, '$.notifications_sent.{kind}') IS NULL "
                  f"OR JSON_EXTRACT(stats, '$.notifications_sent.{kind}') = CAST('false' AS JSON))")
        return [user_id for user_id in candidates if await readiness[kind](user_id)]

    @staticmethod
    async def get_comeback_candidates(limit: int = None, min_feeds: int = None):
        """People worth telling that the bot is back: they played properly, then stopped.

        Ordered by who was still playing latest, in weekly bands, and within a band by
        how much they had played. Recency leads because the people feeding right up to
        the moment the bot went quiet did not choose to stop - it vanished on them - and
        they are the likeliest to want it back. Banding by week rather than comparing
        timestamps exactly keeps that from turning into a meaningless race between two
        people who both stopped the same week; between those two, the one who had played
        more is the better prospect.

        `min_feeds` raises the floor for one run, so a batch can be aimed at a particular
        band and measured on its own before spending the rest of the list.

        Anyone already sent one is excluded by checking the log itself, so the same
        person can never be written to twice however many times this is run, and a partly
        finished send simply carries on where it stopped.
        """
        cutoff = Func.generate_current_timestamp() - config.comeback_dormant_days * 86400
        band = max(1, int(config.comeback_feed_band))
        week = max(1, int(config.comeback_recency_band_days)) * 86400
        rows = await Connection.make_request(
            f"SELECT u.{user_id_column()} FROM {config.users_schema} u "
            f"WHERE JSON_EXTRACT(u.stats, '$.pig_fed') >= %s "
            f"AND (JSON_EXTRACT(u.history, '$.feed_history[last]') IS NULL "
            f"     OR JSON_EXTRACT(u.history, '$.feed_history[last]') < %s) "
            # already written to - matches the way idx_user_timestamp is declared
            f"AND NOT EXISTS (SELECT 1 FROM {config.logs_schema} l "
            f"                WHERE l.log_type = 'come_back_notification' "
            f"                AND CAST(l.data->>'$.user_id' AS UNSIGNED) "
            f"                    = CAST(u.{user_id_column()} AS UNSIGNED)) "
            # latest to stop first, by week, then the most played inside each week.
            # NULLs land last under DESC, which is right - somebody with no recorded
            # last feed is the coldest lead there is
            f"ORDER BY FLOOR(JSON_EXTRACT(u.history, '$.feed_history[last]') / {week}) DESC, "
            f"         FLOOR(JSON_EXTRACT(u.stats, '$.pig_fed') / {band}) DESC, "
            f"         JSON_EXTRACT(u.stats, '$.pig_fed') DESC"
            f"{f' LIMIT {int(limit)}' if limit else ''}",
            params=(min_feeds if min_feeds is not None else config.comeback_min_feeds,
                    cutoff),
            commit=False, fetch=True, fetchall=True)
        return [row[0] for row in (rows or ())]

    @staticmethod
    async def get_user_position(user_id, order_by: str = None, where: str = None, guild=None):
        users = await Tech.get_all_users(order_by=order_by, where=where, guild=guild)
        if str(user_id) in users:
            return users.index(str(user_id))

    @staticmethod
    async def get_all_guilds():
        id_list = await Connection.make_request('SELECT id FROM {config.guilds_schema}', commit=False, fetch=True, fetchall=True)
        id_list = [i[0] for i in id_list]
        return id_list

    @staticmethod
    # @aiocache.cached(key="tech.__get_all_items:{user_id}", alias="tech.__get_all_items")
    async def __get_all_items(requirements: tuple = None, exceptions: tuple = None, context: str = None):
        result = []
        requirements = () if requirements is None else requirements
        exceptions = () if exceptions is None else exceptions
        for k, item in config.items.items():
            # flattened so a requirement can name a field without knowing which config
            # it ended up in, and so passing a context filters on that context's values
            v = config.item_in_context(item, context)
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
    async def clear_get___all_items_cache(params):
        try:
            config.db_caches['tech.__get_all_items'].pop(params)
        except KeyError:
            pass

    @staticmethod
    # @aiocache.cached(key_builder=lambda f, *args, **kwargs: f"tech.get_all_items:{kwargs.get('user_id')}_{kwargs.get('requirements')}_{kwargs.get('exceptions')}", alias="tech.get_all_items")
    async def get_all_items(requirements: tuple = None, exceptions: tuple = None, user_id=None,
                            context: str = None, inventory: dict = None):
        """
        :type requirements: object
            Example: (("rarity", "3"),) - it will return only items with rarity=3
        :param exceptions:
            Example: (("type", "skin"),) - it will return everything except items with type=skin
        :param user_id:
            If user_id is specified, it will return items that are present in the user's inventory
        :param inventory:
            An inventory to filter against directly, for owners that are not users - a
            guild pig keeps its things in the guild row, so there is no user_id to look up
        """
        result = await Tech._Tech__get_all_items(requirements, exceptions, context)
        if inventory is not None:
            return [i for i in result if await Item.get_amount(i, inventory=inventory) != 0]
        if user_id is not None:
            result = [i for i in result if await Item.get_amount(i, user_id) != 0]
            await Tech.clear_get_all_items_cache((requirements, exceptions, user_id))
        return result

    @staticmethod
    async def get_categorized_items(user_id, inventory_type: str):
        """
        Returns {category_key: [item_id, ...]} for an inventory or wardrobe list.
        'all' is always the first key; for 'wardrobe' the rest are raw skin types.
        Keys are raw ids - translating them is up to the caller.
        """
        items = await Tech.get_all_items((('inventory_type', inventory_type),), user_id=user_id)
        if inventory_type != 'wardrobe':
            types = await asyncio.gather(*(Item.get_type(i) for i in items))
            return {'all': [i for _, i in sorted(zip(types, items), key=lambda pair: pair[0] or '')]}
        skin_types = await asyncio.gather(*(Item.get_skin_type(i) for i in items))
        categorized = {'all': [i for _, i in sorted(zip(skin_types, items), key=lambda pair: pair[0] or '')]}
        for item_type in sorted({t for t in skin_types if t is not None}):
            categorized[item_type] = await Tech.get_all_items((('skin_config', 'type', item_type),))
        return categorized

    @staticmethod
    async def clear_get_all_items_cache(params):
        try:
            config.db_caches['tech.get_all_items'].pop(params)
        except KeyError:
            pass

    @staticmethod
    async def fix_settings_structure_for_all_users():
        users = await Tech.get_all_users()
        for user in users:
            await Tech.fix_settings_structure(user)
            await asyncio.sleep(0.1)

    @staticmethod
    async def fix_settings_structure(user_id):
        settings = await User.get_settings(user_id)
        if settings is None:
            settings = {}
        for key, value in config.user_settings.items():
            if key not in settings:
                settings[key] = value
        await User.set_new_settings(user_id, settings)
