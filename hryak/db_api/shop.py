import asyncio
import json
import random

import aiocache
from cachetools import cached

from .connection import Connection
from .item import Item
from .tech import Tech
from .user import User
from ..functions import Func
from hryak import config


class Shop:

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="shop.get_data")
    async def get_data(shop_id=None):
        if shop_id is None:
            query = f"SELECT data FROM {config.shop_schema} ORDER BY id DESC LIMIT 1"
        else:
            query = f"SELECT data FROM {config.shop_schema} WHERE id = {shop_id}"
        result = await Connection.make_request(
            query,
            commit=False,
            fetch=True
        )
        if result is not None:
            return json.loads(result)

    @staticmethod
    async def clear_get_data_cache(shop_id: int = None):
        if shop_id is None:
            await Func.clear_db_cache('shop.get_data', Shop.get_data)
        else:
            await Func.clear_db_cache('shop.get_data', Shop.get_data, str(shop_id))

    @staticmethod
    async def is_item_in_shop(item_id, shop_id=None):
        shop_pages =await Shop.get_data(shop_id)
        for shop in shop_pages:
            if item_id in shop_pages[shop]:
                return True
        return False

    @staticmethod
    async def get_consumables_shop(shop_id=None):
        data =await Shop.get_data(shop_id)
        return data['consumables_shop']

    @staticmethod
    async def get_tools_shop(shop_id=None):
        data =await Shop.get_data(shop_id)
        return data['tools_shop']

    @staticmethod
    async def get_daily_shop(shop_id=None):
        data =await Shop.get_data(shop_id)
        return data['daily_shop']

    @staticmethod
    async def get_case_shop(shop_id=None):
        data =await Shop.get_data(shop_id)
        return data['case_shop']

    @staticmethod
    async def get_coins_shop(shop_id=None):
        data =await Shop.get_data(shop_id)
        return data['coins_shop']

    @staticmethod
    async def get_premium_skins_shop(shop_id: int = None):
        data =await Shop.get_data(shop_id)
        return data['premium_skins_shop']

    @staticmethod
    async def get_update_timestamp(shop_id: int = None):
        if shop_id is None:
            query = f"SELECT timestamp FROM {config.shop_schema} ORDER BY id DESC LIMIT 1"
        else:
            query = f"SELECT timestamp FROM {config.shop_schema} WHERE id = {shop_id}"
        result = await Connection.make_request(
            query,
            commit=False,
            fetch=True,
            fetch_first=True
        )
        if result is not None and result[0] is not None:
            return int(result[0])

    @staticmethod
    async def add_shop_state():

        data = {
            'consumables_shop': [],
            'tools_shop': [],
            'daily_shop':await Shop.generate_shop_daily_items(),
            'case_shop': [],
            'premium_skins_shop': [],
            'coins_shop': [f'coins.a={k}.p={round(v)}.c=hollars' for k, v in config.coins_prices.items()],
        }
        for i in ["laxative", 'compound_feed', "activated_charcoal", "milk"]:
            data['consumables_shop'].append(f'{i}.a={1}.p={await Item.get_market_price(i)}.c={await Item.get_market_price_currency(i)}')
        for i in ["knife", "grill"]:
            data['tools_shop'].append(f'{i}.a={1}.p={await Item.get_market_price(i)}.c={await Item.get_market_price_currency(i)}')
        for i in ["common_case", "rare_case"]:
            data['case_shop'].append(f'{i}.a={1}.p={await Item.get_market_price(i)}.c={await Item.get_market_price_currency(i)}')
        for i in sorted(await Tech.get_all_items((('shop_category', 'premium_skins'),))):
            data['premium_skins_shop'].append(
                f'{i}.a={1}.p={await Item.get_market_price(i)}.c={await Item.get_market_price_currency(i)}')
        async def get_price(i):
            return await Item.get_market_price(i)

        prices = await asyncio.gather(*(Item.get_market_price(x) for x in set(data['premium_skins_shop'])))
        sorted_items = [x for _, x in sorted(zip(prices, set(data['premium_skins_shop'])), key=lambda pair: pair[0], reverse=True)]
        data['premium_skins_shop'] = sorted_items
        await Connection.make_request(
            f"INSERT INTO {config.shop_schema} (timestamp, data) "
            f"VALUES ('{Func.generate_current_timestamp()}', %s)",
            params=(json.dumps(data),)
        )
        await Shop.clear_get_data_cache()

    @staticmethod
    async def generate_shop_daily_items():
        daily_shop = []
        for key in config.daily_shop_items_types.keys():
            if key == 'other':
                exceptions = []
                daily_shop_items_types_copy = config.daily_shop_items_types.copy()
                daily_shop_items_types_copy.pop('other')
                for i in daily_shop_items_types_copy:
                    exceptions.append(('skin_config', 'type', i))
                exceptions = tuple(exceptions)
                for i in random.sample(await Tech.get_all_items(requirements=(('shop_category', 'daily'),), exceptions=exceptions),
                                       config.daily_shop_items_types[key]):
                    daily_shop.append(f'{i}.a={1}.p={await Item.get_market_price(i)}.c={await Item.get_market_price_currency(i)}')
            else:
                for i in random.sample(
                        await Tech.get_all_items(requirements=(('shop_category', 'daily'), ('skin_config', 'type', key))),
                        config.daily_shop_items_types[key]):
                    daily_shop.append(f'{i}.a={1}.p={await Item.get_market_price(i)}.c={await Item.get_market_price_currency(i)}')
        unique_items = list(set(daily_shop))
        price_tasks = [Item.get_market_price(x) for x in unique_items]
        prices = await asyncio.gather(*price_tasks)
        return [x for _, x in sorted(zip(prices, unique_items), key=lambda p: p[0], reverse=True)]

    @staticmethod
    async def is_item_in_cooldown(user_id, item_id):
        cooldown_once_for, cooldown_in = await Item.get_shop_cooldown(item_id)
        if cooldown_once_for is not None and await User.get_count_of_recent_bought_items(user_id, cooldown_in,
                                                                                   [await Item.clean_id(
                                                                                       item_id)]) >= cooldown_once_for:
            return True
        return False

    @staticmethod
    async def get_timestamp_of_cooldown_pass(user_id, item_id):
        cooldown_once_for, cooldown_in = await Item.get_shop_cooldown(item_id)
        if cooldown_once_for is None:
            return
        history = await User.get_recent_bought_items(user_id, cooldown_in)
        if not history:
            return
        return Func.generate_current_timestamp() + (cooldown_in - (
                Func.generate_current_timestamp() - list(history[0].values())[0]))
