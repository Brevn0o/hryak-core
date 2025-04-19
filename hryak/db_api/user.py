import asyncio
import datetime
import json, random

import aiocache

from .connection import Connection
from ..functions import Func, translate
from .history import History
from hryak import config


class User:

    @staticmethod
    async def fix_settings_structure_for_all_users():
        for key, value in config.user_settings.items():
            await Connection.make_request(
                f"UPDATE {config.users_schema} SET settings = JSON_INSERT(settings, '$.{key}', %s) "
                f"WHERE JSON_EXTRACT(settings, '$.{key}') IS NULL",
                params=(value,)
            )

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

        await Connection.make_request(
            f"INSERT INTO {config.users_schema} (id, created, pig, settings, inventory, stats, events, history, rating, orders) "
            f"VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            params=(
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
        await User.add_item(user_id, 'common_case')

    @staticmethod
    async def exists(user_id):
        result = await Connection.make_request(
            f"SELECT EXISTS(SELECT 1 FROM {config.users_schema} WHERE id = {user_id})",
            commit=False,
            fetch=True
        )
        return bool(result)

    @staticmethod
    @aiocache.cached(ttl=86400)
    async def get_user(client, user_id):
        user = client.get_user(int(user_id))
        if user is None:
            user = await client.fetch_user(int(user_id))
        return user

    @staticmethod
    async def get_name(client, user_id):
        user = await User.get_user(client, user_id)
        return user.display_name

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="user.get_inventory")
    async def get_inventory(user_id: str):
        result = await Connection.make_request(
            f"SELECT inventory FROM {config.users_schema} WHERE id = {user_id}",
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
    async def add_item(user_id, item_id, amount: int = 1, log: bool = True):
        inventory = await User.get_inventory(str(user_id))
        amount = round(amount)
        if item_id in inventory:
            inventory[item_id]['amount'] += amount
        else:
            inventory[item_id] = {}
            inventory[item_id]['amount'] = amount
        await User.set_new_inventory(user_id, inventory)
        if log:
            await Func.add_log('item_generated',
                               user_id=user_id,
                               item_id=item_id,
                               amount=amount)

    @staticmethod
    async def remove_item(user_id, item_id, amount: int = 1, log: bool = True):
        await User.add_item(user_id, item_id, -amount, log=False)
        if log:
            await Func.add_log('item_burned',
                               user_id=user_id,
                               item_id=item_id,
                               amount=amount)

    @staticmethod
    async def transfer_item(from_user_id, to_user2_id, item_id, amount: int = 1):
        await User.remove_item(from_user_id, item_id, amount, log=False)
        await User.add_item(to_user2_id, item_id, amount, log=False)
        await Func.add_log('item_transfer',
                           from_user_id=from_user_id,
                           to_user2_id=to_user2_id,
                           item_id=item_id,
                           amount=amount)

    @staticmethod
    async def set_new_inventory(user_id, new_inventory):
        new_inventory = json.dumps(new_inventory, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET inventory = %s WHERE id = {user_id}",
            params=(new_inventory,)
        )
        await User.clear_get_inventory_cache(user_id)

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="user.get_settings")
    async def get_settings(user_id: int):
        result = await Connection.make_request(
            f"SELECT settings FROM {config.users_schema} WHERE id = %s",
            params=(user_id,),
            commit=False,
            fetch=True
        )
        print(result)
        if result is not None:
            return json.loads(result)
        else:
            return {}

    @staticmethod
    async def clear_get_settings_cache(user_id: int):
        await Func.clear_db_cache('user.get_settings', User.get_settings, (user_id,))

    @staticmethod
    async def set_new_settings(user_id: int, new_settings):
        new_settings = json.dumps(new_settings, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET settings = %s WHERE id = %s",
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
            f"SELECT created FROM {config.users_schema} WHERE id = {user_id}",
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
            f"SELECT rating FROM {config.users_schema} WHERE id = {user_id}",
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
            f"UPDATE {config.users_schema} SET rating = '{new_rating}' WHERE id = {user_id}"
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
            f"SELECT orders FROM {config.users_schema} WHERE id = {user_id}",
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
            f"UPDATE {config.users_schema} SET orders = '{new_orders}' WHERE id = {user_id}"
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
