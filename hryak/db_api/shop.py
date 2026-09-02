import asyncio
import datetime
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
    def schema(context: str = None):
        """Which table a shop lives in - the individual one, or the servers' own."""
        if context is None:
            context = config.item_default_context
        return config.shop_schema if context == config.item_default_context else config.server_shop_schema

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="shop.get_data")
    async def get_data(shop_id=None, context: str = None):
        params = None
        schema = Shop.schema(context)
        if shop_id is None:
            query = f"SELECT data FROM {schema} ORDER BY id DESC LIMIT 1"
        else:
            query = f"SELECT data FROM {schema} WHERE id = %s"
            params = (shop_id,)
        result = await Connection.make_request(
            query,
            params=params,
            commit=False,
            fetch=True
        )
        if result is not None:
            return json.loads(result)

    @staticmethod
    async def clear_get_data_cache(shop_id: int = None, context: str = None):
        if shop_id is None:
            await Func.clear_db_cache('shop.get_data', Shop.get_data)
        else:
            await Func.clear_db_cache('shop.get_data', Shop.get_data, str(shop_id), context)

    @staticmethod
    async def is_item_in_shop(item_id, shop_id=None, context: str = None):
        shop_pages = await Shop.get_data(shop_id, context) or {}
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
    async def get_update_timestamp(shop_id: int = None, context: str = None):
        params = None
        schema = Shop.schema(context)
        if shop_id is None:
            query = f"SELECT timestamp FROM {schema} ORDER BY id DESC LIMIT 1"
        else:
            query = f"SELECT timestamp FROM {schema} WHERE id = %s"
            params = (shop_id,)
        result = await Connection.make_request(
            query,
            params=params,
            commit=False,
            fetch=True,
            fetch_first=True
        )
        # make_request already unwrapped the row, so result is the timestamp itself -
        # indexing it again would take the first character of the string
        if result is not None:
            return int(result)

    @staticmethod
    async def page_order_key(item_id: str, context: str = None):
        """How one item sorts on a shop page.

        Three things, in order. Permanent stock first and seasonal after it, so a page
        reads as the usual shelf with whatever is in season added on the end, rather than
        a limited-time item taking the top slot because it happens to be cheap. Then the
        currency, because a price only means something against another price in the same
        money - five cookies is not cheaper than a hundred and twenty coins, it is a
        different question. Then, inside one currency, the cheapest first.
        """
        item = config.items.get(await Item.clean_id(item_id)) or {}
        seasonal = bool(config.item_in_context(item, context).get(config.item_availability_key))
        currency = await Item.get_market_price_currency(item_id, context)
        rank = config.shop_currency_order.index(currency) \
            if currency in config.shop_currency_order else len(config.shop_currency_order)
        return seasonal, rank, await Item.get_market_price(item_id, context) or 0

    @staticmethod
    async def update():

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
        # the permanent cases in price order, then whatever is in season. Seasonal cases
        # come and go with their window, so the page is whatever is on sale today
        cases = await Tech.get_all_items((('shop_category', 'cases'),), available_only=True)
        case_order = await asyncio.gather(*(Shop.page_order_key(i) for i in cases))
        for _, i in sorted(zip(case_order, cases), key=lambda pair: pair[0]):
            data['case_shop'].append(f'{i}.a={1}.p={await Item.get_market_price(i)}.c={await Item.get_market_price_currency(i)}')
        for i in sorted(await Tech.get_all_items((('shop_category', 'premium_skins'),), available_only=True)):
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
    async def generate_server_weekly_items(shop_category: str):
        """Draws one page's stock, a few of each skin type rather than its whole catalogue.

        Same shape as the daily shop: the page's entry in server_shop_tiers says how many of
        each type to take, and 'other' mops up whatever is not named. Asking for more of a
        type than exists just takes all of them instead of raising.
        """
        wanted = config.server_shop_tiers[shop_category]
        chosen = []
        named = [key for key in wanted if key != 'other']
        for key, amount in wanted.items():
            if key == 'other':
                pool = await Tech.get_all_items(
                    (('shop_category', shop_category),),
                    exceptions=tuple(('skin_config', 'type', i) for i in named),
                    context='server', available_only=True)
            else:
                pool = await Tech.get_all_items(
                    (('shop_category', shop_category), ('skin_config', 'type', key)),
                    context='server', available_only=True)
            pool = [i for i in pool if await Item.get_market_price(i, context='server') is not None]
            chosen += random.sample(pool, min(amount, len(pool)))
        return chosen

    @staticmethod
    def server_shop_pages():
        """Which page each shop_category fills - the rotating tiers, then the permanent one."""
        return {**{tier: f'{tier}_shop' for tier in config.server_shop_tiers},
                'always': 'permanent_shop'}

    @staticmethod
    async def update_server():
        """Builds the servers' shop. Cosmetics only, priced from each item's server_config -
        an item with no server price there is simply not sold to servers."""
        pages = Shop.server_shop_pages()
        data = {page: [] for page in pages.values()}
        for shop_category, page in pages.items():
            entries = []
            # a tier rotates a handful of its own bracket; the permanent page really is everything
            items = await Shop.generate_server_weekly_items(shop_category) \
                if shop_category in config.server_shop_tiers \
                else await Tech.get_all_items((('shop_category', shop_category),), context='server',
                                              available_only=True)
            for i in items:
                price = await Item.get_market_price(i, context='server')
                if price is None:
                    continue
                entries.append(f'{i}.a={1}.p={price}'
                               f'.c={await Item.get_market_price_currency(i, context="server")}')
            prices = await asyncio.gather(*(Item.get_market_price(x) for x in entries))
            data[page] = [x for _, x in sorted(zip(prices, entries), key=lambda pair: pair[0], reverse=True)]
        await Connection.make_request(
            f"INSERT INTO {config.server_shop_schema} (timestamp, data) VALUES (%s, %s)",
            params=(Func.generate_current_timestamp(), json.dumps(data))
        )
        await Shop.clear_get_data_cache()

    @staticmethod
    def season_turned_over(since: int, context: str = None):
        """Whether any item came into or went out of season since that moment.

        A rotation on a timer is too coarse for a window on its own: the servers' shop
        turns over on a Sunday, so a season opening on a Tuesday would not be stocked for
        five days and would sit there for six after it closed. Asking each item what it
        would have answered then, against what it answers now, catches the boundary on
        the next loop instead of the next rotation.
        """
        then = datetime.datetime.fromtimestamp(since, datetime.timezone.utc)
        now = datetime.datetime.now(datetime.timezone.utc)
        return any(config.item_available_now(item, context, then)
                   != config.item_available_now(item, context, now)
                   for item in config.items.values())

    @staticmethod
    async def update_server_if_needed():
        """Regenerates the servers' shop once a week, at Sunday 00:00 UTC for everyone,
        and again straight away whenever a season opens or closes.

        Safe to call as often as you like - it decides on its own whether anything is due.
        Returns True if a new shop state was written.
        """
        last_update_timestamp = await Shop.get_update_timestamp(context='server')
        if last_update_timestamp is None or last_update_timestamp < Func.get_week_start() \
                or Shop.season_turned_over(last_update_timestamp, 'server'):
            await Shop.update_server()
            return True
        return False

    @staticmethod
    async def update_if_needed():
        """Regenerates the shop if it has not been generated since midnight, and again
        straight away whenever a season opens or closes.

        Midnight is UTC, matching the weekly rotation and the windows themselves, so a
        season starts at one moment for everybody rather than wherever the bot is running.

        Safe to call as often as you like - it decides on its own whether anything
        is due. Returns True if a new shop state was written.
        """
        last_update_timestamp = await Shop.get_update_timestamp()
        midnight = int(datetime.datetime.now(datetime.timezone.utc)
                       .replace(hour=0, minute=0, second=0, microsecond=0).timestamp())
        if last_update_timestamp is None or last_update_timestamp < midnight \
                or Shop.season_turned_over(last_update_timestamp):
            await Shop.update()
            return True
        return False

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
                for i in random.sample(await Tech.get_all_items(requirements=(('shop_category', 'daily'),), exceptions=exceptions,
                                                               available_only=True),
                                       config.daily_shop_items_types[key]):
                    daily_shop.append(f'{i}.a={1}.p={await Item.get_market_price(i)}.c={await Item.get_market_price_currency(i)}')
            else:
                for i in random.sample(
                        await Tech.get_all_items(requirements=(('shop_category', 'daily'), ('skin_config', 'type', key)),
                                                 available_only=True),
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
