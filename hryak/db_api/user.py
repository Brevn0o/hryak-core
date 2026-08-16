import asyncio
import datetime
import copy
import json, random

import aiocache
import pymysql.err

from .connection import Connection
from .schema import user_id_column
from ..functions import Func, translate
from .logs import Logs
from .history import History
from hryak import config
from .guild_pig import GuildPig

# mysql's error number for a unique-key violation
DUPLICATE_ENTRY = 1062


class User:

    @staticmethod
    async def fix_settings_structure_for_all_users(nested_key_path: str = '', standard_values: dict = None):
        """Fills in any setting a row is missing, including the ones inside a nested setting.

        A dict cannot be handed to the driver as a parameter, so anything that is one goes
        in as json and is then walked into - a row that already has the group but not a
        newer toggle inside it would otherwise keep the gap forever.
        """
        if standard_values is None:
            standard_values = config.user_settings
        for key, value in standard_values.items():
            key_path = f'{nested_key_path}.{key}' if nested_key_path else key
            as_json = isinstance(value, (dict, list))
            await Connection.make_request(
                f"UPDATE {config.users_schema} "
                f"SET settings = JSON_INSERT(settings, '$.{key_path}', "
                f"{'CAST(%s AS JSON)' if as_json else '%s'}) "
                f"WHERE JSON_EXTRACT(settings, '$.{key_path}') IS NULL",
                params=(json.dumps(value) if as_json else value,)
            )
            if isinstance(value, dict):
                await User.fix_settings_structure_for_all_users(key_path, value)

    @staticmethod
    async def register_user_if_not_exists(user_id):
        if not await User.exists(user_id):
            await User.register(user_id)

    @staticmethod
    async def register(user_id: int):
        stats = json.dumps(config.default_stats)
        pig = config.default_pig.copy()
        body = random.choice(config.default_pig_body_genetic)
        pig['genetic']['body'] = body
        pig['genetic']['tail'] = body
        pig['genetic']['left_ear'] = body
        pig['genetic']['right_ear'] = body
        pig['genetic']['nose'] = body
        eyes = random.choice(config.default_pig_eyes_genetic)
        pig['genetic']['right_eye'] = eyes
        pig['genetic']['left_eye'] = eyes
        pupils = random.choice(config.default_pig_pupils_genetic)
        pig['genetic']['right_pupil'] = pupils
        pig['genetic']['left_pupil'] = pupils
        pig['name'] = 'Hryak'
        pig = json.dumps(pig)

        unique_primary_id = random.randrange(10000000, 99999999)
        while await User.exists(unique_primary_id, column='id'):
            unique_primary_id = random.randrange(10000000, 99999999)


        try:
            await Connection.make_request(
                f"INSERT INTO {config.users_schema} (id, {user_id_column()}, created, pig, settings, inventory, stats, events, history, rating, orders) "
                f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                params=(
                    unique_primary_id,
                    user_id,
                    Func.generate_current_timestamp(),
                    pig,
                    json.dumps(config.user_settings),
                    json.dumps({}),
                    stats,
                    json.dumps({}),
                    json.dumps(config.default_history),
                    json.dumps({}),
                    json.dumps({})
                )
            )
        except pymysql.err.IntegrityError as e:
            # Somebody else registered this id in between the exists() check and here.
            #
            # It is not a rare accident: discord.py's parse_interaction_create both hands
            # the interaction to the command tree (which creates its own task) and fires
            # on_interaction (another task), and both paths register. So every single
            # interaction from an account that has no row yet runs two registrations at
            # once, and one of them has to lose.
            #
            # The winner's row is in place and the winner does the log and the gift below,
            # so the loser has nothing left to do. Anything other than a duplicate key is
            # a real failure and still raised.
            if e.args and e.args[0] == DUPLICATE_ENTRY:
                return
            raise
        # only reached by whoever actually created the row, so the gift is granted once
        # however many callers raced for it
        await Logs.add('user_registered', user_id=user_id)
        await User.add_item(user_id, 'common_case', reason='registration_gift')

    @staticmethod
    async def exists(user_id, column: str = None):
        if column is None:
            column = user_id_column()
        result = await Connection.make_request(
            f"SELECT EXISTS(SELECT 1 FROM {config.users_schema} WHERE {column} = %s)",
            params=(user_id,),
            commit=False,
            fetch=True
        )
        return bool(result)

    @staticmethod
    async def transfer_data(from_user_id, to_user_id, overwrite: bool = False):
        """Moves a whole account onto another platform id.

        Nothing is actually copied. The row keeps its internal id, so pig, inventory,
        stats, events, history and orders come along untouched - only the platform id
        on the row changes, plus the few places where other rows point at the user by
        that id instead of by the internal one.

        Returns Status.NOT_EXIST when there is nothing to move, and Status.ALREADY_USED
        when to_user_id already has an account - pass overwrite=True to delete it first,
        which is not reversible.
        """
        from .pig import Pig
        from ..statuses import Status

        from_user_id, to_user_id = str(from_user_id), str(to_user_id)
        if from_user_id == to_user_id:
            return Status.SUCCESS
        if not await User.exists(from_user_id):
            return Status.NOT_EXIST
        if await User.exists(to_user_id):
            if not overwrite:
                return Status.ALREADY_USED
            await Connection.make_request(
                f"DELETE FROM {config.users_schema} WHERE {user_id_column()} = %s",
                params=(to_user_id,)
            )

        await Connection.make_request(
            f"UPDATE {config.users_schema} SET {user_id_column()} = %s WHERE {user_id_column()} = %s",
            params=(to_user_id, from_user_id)
        )

        # rating is keyed by the id of whoever left the rate, so the user appears in
        # everyone else's row. if both ids rated the same person, the moved one wins
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET rating = JSON_REMOVE("
            f"JSON_SET(rating, CONCAT('$.\"', %s, '\"'), JSON_EXTRACT(rating, CONCAT('$.\"', %s, '\"'))), "
            f"CONCAT('$.\"', %s, '\"')) "
            f"WHERE JSON_CONTAINS_PATH(rating, 'one', CONCAT('$.\"', %s, '\"'))",
            params=(to_user_id, from_user_id, from_user_id, from_user_id)
        )
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET pig = JSON_SET(pig, '$.pregnant_by', %s) "
            f"WHERE JSON_UNQUOTE(JSON_EXTRACT(pig, '$.pregnant_by')) = %s",
            params=(to_user_id, from_user_id)
        )
        await Connection.make_request(
            f"UPDATE {config.promocodes_schema} SET users_used = JSON_REPLACE("
            f"users_used, JSON_UNQUOTE(JSON_SEARCH(users_used, 'one', %s)), %s) "
            f"WHERE JSON_SEARCH(users_used, 'one', %s) IS NOT NULL",
            params=(from_user_id, to_user_id, from_user_id)
        )

        for user_id in (from_user_id, to_user_id):
            await User.clear_get_inventory_cache(user_id)
            await User.clear_get_settings_cache(user_id)
            await Pig.clear_get_pig_cache(user_id)
            await History.clear_get_history_cache(user_id)
        # the rename edited other people's rating blobs, so drop the whole alias
        await Func.clear_db_cache('user.get_rating', User.get_rating)
        return Status.SUCCESS

    @staticmethod
    @aiocache.cached(ttl=86400)
    async def get_discord_user(discord_client, user_id):
        user = discord_client.get_user(int(user_id))
        if user is None:
            user = await discord_client.fetch_user(int(user_id))
        return user

    @staticmethod
    async def get_discord_user_name(discord_client, user_id):
        user = await User.get_discord_user(discord_client, user_id)
        return user.display_name

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="user.get_inventory")
    async def get_inventory(user_id: str):
        result = await Connection.make_request(
            f"SELECT inventory FROM {config.users_schema} WHERE {user_id_column()} = %s",
            params=(user_id,),
            commit=False,
            fetch=True
        )
        if result is not None:
            return json.loads(result)
        else:
            return {}

    @staticmethod
    async def clear_get_inventory_cache(user_id):
        await Func.clear_db_cache('user.get_inventory', User.get_inventory, (user_id,))


    @staticmethod
    async def set_item_amount(user_id, item_id, amount: int = 1):
        inventory = await User.get_inventory(str(user_id))
        inventory[item_id] = {}
        inventory[item_id]['item_id'] = item_id
        inventory[item_id]['amount'] = amount
        await User.set_new_inventory(user_id, inventory)

    @staticmethod
    def add_item_to_inventory(inventory, item_id, amount: int = 1):
        """Hands back a new inventory with the item added.

        Kept storage-free so the guild pig can add items by the same rule instead of
        repeating it - the same way set_skin_to_options is shared.
        """
        inventory = inventory.copy()
        amount = round(amount)
        if item_id in inventory:
            inventory[item_id] = {**inventory[item_id], 'amount': inventory[item_id]['amount'] + amount}
        else:
            inventory[item_id] = {'amount': amount}
        return inventory

    @staticmethod
    async def add_item(user_id, item_id, amount: int = 1, log: bool = True,
                       reason: str = None):
        inventory = await User.get_inventory(str(user_id))
        amount = round(amount)
        await User.set_new_inventory(user_id, User.add_item_to_inventory(inventory, item_id, amount))
        if log:
            await Logs.add('item_generated',
                           user_id=user_id,
                           item_id=item_id,
                           amount=amount,
                           reason=reason)

    @staticmethod
    async def remove_item(user_id, item_id, amount: int = 1, log: bool = True,
                          reason: str = None):
        await User.add_item(user_id, item_id, -amount, log=False)
        if log:
            await Logs.add('item_burned',
                           user_id=user_id,
                           item_id=item_id,
                           amount=amount,
                           reason=reason)

    @staticmethod
    async def transfer_item(from_user=None, to_user=None, item_id=None, amount: int = 1,
                            from_guild=None, to_guild=None, log: bool = True,
                            reason: str = None):
        """Moves items between any two holders.

        Put a user id in from_user/to_user and a guild id in from_guild/to_guild - which
        slot you fill says what kind of holder it is, so there is nothing to look up and
        no flag to get wrong. Exactly one of each pair has to be given.
        """
        if (from_user is None) == (from_guild is None):
            raise ValueError('give exactly one of from_user or from_guild')
        if (to_user is None) == (to_guild is None):
            raise ValueError('give exactly one of to_user or to_guild')
        if from_user is not None:
            await User.remove_item(from_user, item_id, amount, log=False)
        else:
            await GuildPig.remove_item(from_guild, item_id, amount)
        if to_user is not None:
            await User.add_item(to_user, item_id, amount, log=False)
        else:
            await GuildPig.add_item(to_guild, item_id, amount)
        if log:
            await Logs.add('item_transfer',
                           from_user=from_user,
                           to_user=to_user,
                           from_guild=from_guild,
                           to_guild=to_guild,
                           item_id=item_id,
                           amount=amount,
                           reason=reason)

    @staticmethod
    async def set_new_inventory(user_id, new_inventory):
        new_inventory = json.dumps(new_inventory, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET inventory = %s WHERE {user_id_column()} = %s",
            params=(new_inventory, user_id)
        )
        await User.clear_get_inventory_cache(user_id)

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="user.get_settings")
    async def get_raw_settings(user_id: int):
        """Whatever is actually stored in the column, nothing filled in."""
        result = await Connection.make_request(
            f"SELECT settings FROM {config.users_schema} WHERE {user_id_column()} = %s",
            params=(user_id,),
            commit=False,
            fetch=True
        )
        if result is not None:
            return json.loads(result)
        else:
            return {}

    @staticmethod
    async def get_settings(user_id: int):
        """Always returns every setting, even for a row that has none of them.

        Each getter reads its key directly, so a setting that is merely absent - a user
        registered before it existed, or a row the structure fix has not reached yet - used
        to raise rather than read as its default.

        Filled in outside the cache on purpose: a key added to user_settings then reaches
        people who are already cached, instead of waiting out a shared redis entry.
        """
        return {**copy.deepcopy(config.user_settings), **await User.get_raw_settings(user_id)}

    @staticmethod
    async def clear_get_settings_cache(user_id: int):
        await Func.clear_db_cache('user.get_settings', User.get_raw_settings, (user_id,))

    @staticmethod
    async def set_new_settings(user_id: int, new_settings):
        new_settings = json.dumps(new_settings, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET settings = %s WHERE {user_id_column()} = %s",
            params=(new_settings, user_id)
        )
        await User.clear_get_settings_cache(user_id)

    @staticmethod
    async def set_language(user_id: int, language):
        settings = await User.get_settings(user_id)
        settings['language'] = language
        await User.set_new_settings(user_id, settings)

    @staticmethod
    async def get_language(user_id: int):
        settings = await User.get_settings(user_id)
        return settings['language']

    @staticmethod
    async def get_notifications(user_id: int):
        """Every notification toggle, defaults filled in.

        get_settings only merges the top level, so somebody who has 'notifications' stored
        from before a toggle existed would be missing that one key - filled in here so a
        new kind of reminder reads as off rather than raising.
        """
        settings = await User.get_settings(user_id)
        return {**copy.deepcopy(config.user_settings['notifications']),
                **(settings.get('notifications') or {})}

    @staticmethod
    async def get_notification(user_id: int, kind: str):
        return (await User.get_notifications(user_id)).get(kind, False)

    @staticmethod
    async def set_notification(user_id: int, kind: str, enabled: bool):
        """Turns one kind of reminder on or off. Returns whether it actually changed
        anything - False for a kind that does not exist, so a stray custom_id cannot
        write a garbage key into somebody's settings."""
        if kind not in config.user_settings['notifications']:
            return False
        settings = await User.get_settings(user_id)
        notifications = await User.get_notifications(user_id)
        notifications[kind] = bool(enabled)
        settings['notifications'] = notifications
        await User.set_new_settings(user_id, settings)
        return True

    @staticmethod
    async def set_top_participation(user_id: int, participate: bool):
        settings = await User.get_settings(user_id)
        settings['top_participate'] = participate
        await User.set_new_settings(user_id, settings)

    @staticmethod
    async def get_top_participation(user_id):
        settings = await User.get_settings(user_id)
        return settings['top_participate']

    @staticmethod
    async def get_registration_timestamp(user_id: int):
        result = await Connection.make_request(
            f"SELECT created FROM {config.users_schema} WHERE {user_id_column()} = %s",
            params=(user_id,),
            commit=False,
            fetch=True
        )
        return int(result)

    @staticmethod
    async def get_age(user_id: int):
        return Func.generate_current_timestamp() - await User.get_registration_timestamp(user_id)

    @staticmethod
    async def is_blocked(user_id: int):
        settings = await User.get_settings(user_id)
        return settings['blocked']

    @staticmethod
    async def set_block(user_id: int, block: bool, reason: str = None):
        settings = await User.get_settings(user_id)
        settings['blocked'] = block
        await User.set_block_reason(user_id, reason)
        await User.set_new_settings(user_id, settings)

    @staticmethod
    async def set_block_reason(user_id: int, reason: str):
        settings = await User.get_settings(user_id)
        settings['block_reason'] = reason
        await User.set_new_settings(user_id, settings)

    @staticmethod
    async def get_block_reason(user_id: int):
        settings = await User.get_settings(user_id)
        return settings['block_reason']

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="user.get_rating")
    async def get_rating(user_id):
        result = await Connection.make_request(
            f"SELECT rating FROM {config.users_schema} WHERE {user_id_column()} = %s",
            params=(user_id,),
            commit=False,
            fetch=True,
        )
        if result is not None:
            return json.loads(result)
        else:
            return {}

    @staticmethod
    async def clear_get_rating_cache(user_id: int):
        await Func.clear_db_cache('user.get_rating', User.get_rating, (user_id,))

    @staticmethod
    async def set_new_rating(user_id, new_rating):
        new_rating = json.dumps(new_rating, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET rating = %s WHERE {user_id_column()} = %s",
            params=(new_rating, user_id)
        )
        await User.clear_get_rating_cache(user_id)

    @staticmethod
    async def append_rate(user_id: int, rated_by_id: int, rate: int):
        rating = await User.get_rating(user_id)
        if str(rated_by_id) not in rating:
            rating[str(rated_by_id)] = {}
        rating[str(rated_by_id)]['rate_timestamp'] = Func.generate_current_timestamp()
        rating[str(rated_by_id)]['rate'] = rate
        await User.set_new_rating(user_id, rating)

    @staticmethod
    async def get_rate_number(user_id: int, rater_id: int):
        rating = await User.get_rating(user_id)
        rate = 0
        if str(rater_id) in rating:
            if 'rate' in rating[str(rater_id)]:
                rate = rating[str(rater_id)]['rate']
        return rate

    @staticmethod
    async def get_amount_of_positive_ratings(user_id: int):
        rating = await User.get_rating(user_id)
        amount = 0
        for rater_id in rating:
            if await User.get_rate_number(user_id, rater_id) == 1:
                amount += 1
        return amount

    @staticmethod
    async def get_amount_of_negative_ratings(user_id: int):
        rating = await User.get_rating(user_id)
        amount = 0
        for rater_id in rating:
            if await User.get_rate_number(user_id, rater_id) == -1:
                amount += 1
        return amount

    @staticmethod
    async def get_rating_total_number(user_id: int):
        rating = await User.get_rating(user_id)
        number = 0
        for rater_id in rating:
            number += await User.get_rate_number(user_id, rater_id)
        return number

    @staticmethod
    async def get_recent_bought_items(user_id: int, seconds: float):
        current_time = datetime.datetime.now()
        recent_items = []
        for item in await History.get_shop_history(user_id):
            for key, value in item.items():
                timestamp = datetime.datetime.fromtimestamp(value)
                time_diff = current_time - timestamp
                if time_diff.total_seconds() < seconds:
                    recent_items.append({key: value})
        return recent_items

    @staticmethod
    async def get_count_of_recent_bought_items(user_id, seconds, items_):
        count = 0
        recent_items = await User.get_recent_bought_items(user_id, seconds)
        for item in recent_items:
            if list(item.keys())[0] in items_:
                count += 1
        return count

    @staticmethod
    async def get_orders(user_id):
        result = await Connection.make_request(
            f"SELECT orders FROM {config.users_schema} WHERE {user_id_column()} = %s",
            params=(user_id,),
            commit=False,
            fetch=True,
        )
        if result is not None:
            return json.loads(result)
        else:
            return {}

    @staticmethod
    async def set_new_orders(user_id, new_orders):
        new_orders = json.dumps(new_orders, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET orders = %s WHERE {user_id_column()} = %s",
            params=(new_orders, user_id)
        )

    @staticmethod
    async def create_new_order(user_id, order_id: str, items: dict, platform: str = 'aaio'):
        orders = await User.get_orders(user_id)
        orders[order_id] = {'status': 'in_process',
                            'items': items,
                            'platform': platform,
                            'timestamp': Func.generate_current_timestamp()}
        await User.set_new_orders(user_id, orders)

    @staticmethod
    async def order_exists(user_id, order_id: str):
        orders = await User.get_orders(user_id)
        if order_id in orders:
            return orders[order_id]

    @staticmethod
    async def get_order(user_id, order_id: str):
        orders = await User.get_orders(user_id)
        if order_id in orders:
            return orders[order_id]

    @staticmethod
    async def get_order_db_status(user_id, order_id: str):
        order = await User.get_order(user_id, order_id)
        return order['status']

    @staticmethod
    async def get_order_items(user_id, order_id: str):
        order = await User.get_order(user_id, order_id)
        return order['items']

    @staticmethod
    async def get_order_platform(user_id, order_id: str):
        order = await User.get_order(user_id, order_id)
        return order['platform']

    @staticmethod
    async def delete_order(user_id, order_id):
        orders = await User.get_orders(user_id)
        if order_id in orders:
            orders.pop(order_id)
        await User.set_new_orders(user_id, orders)
