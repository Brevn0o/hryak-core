import asyncio
import datetime
import math

import aiocache
import numpy as np
from scipy.interpolate import PchipInterpolator

from . import config
from .functions import Func
from .db_api import *


class GameFunc:

    @staticmethod
    async def calculate_buff_multipliers(user_id, use_buffs: bool = False, client=None):
        res = config.base_buff_multipliers.copy()
        pig_buffs = await GameFunc.get_all_pig_buffs(user_id, client)
        pig_buffs_raw = {i: [] for i in res.copy()}
        for buff in pig_buffs:
            if use_buffs and buff in ['laxative', 'compound_feed', 'cookie']:
                await Pig.remove_buff(user_id, buff)
            for multiplier_name, multiplier in pig_buffs[buff].items():
                pig_buffs_raw[multiplier_name].append(multiplier)
        pig_buffs_raw = {k: sorted(v, key=lambda x: x.startswith('x')) for k, v in pig_buffs_raw.items()}
        for multiplier_name in pig_buffs_raw:
            for multiplier in pig_buffs_raw[multiplier_name]:
                digit_multiplier = float(multiplier[1:])
                match multiplier[0]:
                    case 'x':
                        res[multiplier_name] *= digit_multiplier
                    case '+':
                        res[multiplier_name] += digit_multiplier
                    case '-':
                        res[multiplier_name] -= digit_multiplier
        res = {k: round(v, 2) for k, v in res.items()}
        return res

    @staticmethod
    async def get_all_pig_buffs(user_id, discord_client=None):
        buffs = {}
        for buff in await Pig.get_buffs(user_id):
            if await Pig.get_buff_amount(user_id, buff) > 0 or not await Pig.buff_expired(user_id, buff):
                buffs[buff] = await Item.get_buffs(buff)
            if discord_client is not None:
                for i in config.bot_guilds:
                    bot_guild = discord_client.get_guild(i)
                    if bot_guild is not None:
                        if bot_guild.get_member(user_id) is not None:
                            buffs['support_server'] = {'weight': 'x1.05'}
        buffs['pig_weight'] = {}
        pchip_function = PchipInterpolator(np.array([0, 50, 100, 500, 5000, 20000, 1000000]),
                                           np.array([0, .5, 1, 3, 5, 10, 30]))
        buffs['pig_weight']['pooping'] = f'+{round(float(pchip_function(await Pig.get_weight(user_id))), 2)}'
        pchip_function = PchipInterpolator(np.array([0, 20, 50, 1000, 10000, 1000000]),
                                           np.array([0, 0, 1, 1.5, 5, 10]))
        buffs['pig_weight']['vomit_chance'] = f'x{round(float(pchip_function(await Pig.get_weight(user_id))), 2)}'
        return buffs

    @staticmethod
    async def get_user_wealth(user_id):
        wealth = {}
        start_time = datetime.datetime.now()
        print(start_time)
        inventory = await User.get_inventory(user_id)
        for item_id in inventory:
            wealth_impact = await Item.get_wealth_impact(item_id)
            market_price = await Item.get_market_price(item_id)
            if wealth_impact is not None and market_price is not None:
                currency = await Item.get_market_price_currency(item_id)
                amount = await Item.get_amount(item_id, user_id, inventory=inventory)
                if currency not in wealth:
                    wealth[currency] = 0
                wealth[currency] += amount * market_price * wealth_impact
        print(f"User wealth calculation time: {datetime.datetime.now() - start_time}")
        return wealth

    @staticmethod
    async def calculate_item_tax(item_id, user_id):
        tax = await Item._get_tax(item_id)
        if tax is None:
            return [0, "coins"]
        elif isinstance(tax, list):
            return tax
        elif tax == 'auto':
            return [round(await Item.get_market_price(item_id) * (
                    await GameFunc.get_user_tax_percent(user_id, await Item.get_market_price_currency(item_id)) / 100), 3),
                    await Item.get_market_price_currency(item_id)]
        elif tax.endswith('%'):
            return [round(await Item.get_market_price(item_id) * (float(tax[:-1]) / 100), 3),
                    await Item.get_market_price_currency(item_id)]

    @staticmethod
    async def get_transfer_amount_with_tax(amount, tax):
        amount_with_tax = math.ceil(amount + amount * (tax / 100))
        return amount_with_tax

    @staticmethod
    async def get_guild_pig_weight_bonus(weight):
        """How much the pig's size multiplies its pooping by.

        Deliberately shallow - a pig a hundred times heavier poops about twice as much per
        feeder, not a hundred times. That is what keeps a small server worth feeding, and
        it is sized to cancel out the placing bonus, which runs the other way.
        """
        x, y = config.guild_pig_poop_weight_bonus
        return float(PchipInterpolator(np.array(x), np.array(y))(max(0, weight)))

    @staticmethod
    async def get_trade_total_tax(trade_id):
        total_tax = {}
        for user_id in await Trade.get_users(trade_id):
            for item_id in await Trade.get_items(trade_id, user_id):
                item_tax = await GameFunc.calculate_item_tax(item_id, user_id)
                if item_tax[1] not in total_tax:
                    total_tax[item_tax[1]] = 0
                total_tax[item_tax[1]] += await Trade.get_item_amount(trade_id, user_id, item_id) * item_tax[0]
        return {k: math.ceil(v) for k, v in total_tax.items() if v > 0}

    @staticmethod
    async def calculate_missed_streak_days(user_id):
        return (Func.generate_current_timestamp() - await History.get_last_streak_timestamp(
            user_id)) // config.streak_timeout

    @staticmethod
    async def get_number_of_possible_skin_variations():
        """How many distinct pigs can be assembled - the product of the skins available per slot."""
        counts = {}
        for item_id in await Tech.get_all_items((('type', 'skin'),)):
            skin_type = await Item.get_skin_type(item_id)
            counts[skin_type] = counts.get(skin_type, 0) + 1
        variations = 1
        for number_of_skins in counts.values():
            variations *= number_of_skins
        return variations

    @staticmethod
    async def reset_expired_streaks(delay: float = 1):
        """Zeroes the streak of everyone who has missed more than one streak window.

        Safe to call as often as you like. Sleeps `delay` seconds between users to keep
        the load off the database. Returns how many streaks were reset.
        """
        reset = 0
        for user_id in await Tech.get_all_users(where="JSON_EXTRACT(stats, '$.streak') > 0"):
            if await GameFunc.calculate_missed_streak_days(user_id) > 1:
                await Stats.set_streak(user_id, 0)
                reset += 1
            await asyncio.sleep(delay)
        return reset

    @staticmethod
    async def get_not_compatible_active_skins(user_id, item_id, skins: dict = None):
        """Returns skins worn by the user that are not compatible with item_id

        Pass skins to ask the same question about a pig that is not a user's - a guild pig
        wears its skins in the guild row, so there is no user_id to look them up by.
        """
        if skins is None:
            skins = (await Pig.get(user_id))['skins']
        not_compatible_skins = []
        for _skin in skins:
            _skin = skins[_skin]
            if _skin is None:
                continue
            if await Item.get_not_compatible_skins(item_id) is not None and (
                    item_id in await Item.get_not_compatible_skins(_skin) or await Item.get_skin_type(
                item_id) in await Item.get_not_compatible_skins(_skin)):
                not_compatible_skins.append(_skin)
            elif await Item.get_not_compatible_skins(item_id) is not None and (
                    await Item.get_skin_type(_skin) in await Item.get_not_compatible_skins(
                item_id) or _skin in await Item.get_not_compatible_skins(item_id)):
                not_compatible_skins.append(_skin)
        return not_compatible_skins

    @staticmethod
    async def guild_churn_summary(guild_id):
        """What a server did with the bot, gathered at the moment it removes it.

        Recorded on the way out because most of it stops being answerable afterwards.
        The point is to tell the kinds of leaving apart, which need different fixes:

          never set up    - nobody ran the setup. an onboarding problem, not a game one.
          never used      - set up, but no one ever touched it.
          went quiet      - used for a while, then stopped well before the removal.
          left while used - still being used the day it went. someone chose to remove it.

        Feeding numbers come from the guild pig rather than the log because the pig
        keeps its whole history, while the log only knows about recent events.
        """
        now = Func.generate_current_timestamp()
        joined = await Guild.joined(guild_id)
        summary = {
            'days_present': round((now - joined) / 86400, 1) if joined else None,
            'was_set_up': await GuildPig.is_setup(guild_id),
            'language': await Guild.get_language(guild_id),
        }

        feeds = await GuildPig.get_feeds(guild_id)
        summary['pig_feeds'] = len(feeds)
        summary['pig_feeders'] = len({str(f['user_id']) for f in feeds})
        summary['pig_weight'] = await GuildPig.get_weight(guild_id)
        if feeds:
            last = max(f['timestamp'] for f in feeds)
            first = min(f['timestamp'] for f in feeds)
            summary['days_since_last_feed'] = round((now - last) / 86400, 1)
            if joined:
                summary['days_to_first_feed'] = round((first - joined) / 86400, 1)

        totals = await Connection.make_request(
            f"SELECT COUNT(*), COUNT(DISTINCT CAST(data->>'$.user_id' AS UNSIGNED)), "
            f"MIN(timestamp), MAX(timestamp) FROM {config.logs_schema} "
            f"WHERE log_type = 'command_used' "
            f"AND CAST(data->>'$.guild_id' AS UNSIGNED) = %s",
            params=(guild_id,), fetch=True, fetch_first=False)
        used, users, first_cmd, last_cmd = totals[0] if totals else (0, 0, None, None)
        summary['commands_used'] = int(used or 0)
        summary['command_users'] = int(users or 0)
        if last_cmd:
            summary['days_silent'] = round((now - int(last_cmd)) / 86400, 1)
        if first_cmd and joined:
            # clamped: registration happens on the first command, so the two stamps can
            # land in the same second and round to a confusing -0.0
            summary['days_to_first_command'] = max(0.0, round((int(first_cmd) - joined) / 86400, 1))

        top = await Connection.make_request(
            f"SELECT CAST(data->>'$.command' AS CHAR(64)) c, COUNT(*) n "
            f"FROM {config.logs_schema} WHERE log_type = 'command_used' "
            f"AND CAST(data->>'$.guild_id' AS UNSIGNED) = %s "
            f"GROUP BY c ORDER BY n DESC LIMIT 8",
            params=(guild_id,), fetch=True, fetch_first=False)
        summary['top_commands'] = {row[0]: int(row[1]) for row in (top or ()) if row[0]}
        return summary

    @staticmethod
    async def pay_tax(user_id, amount, currency):
        await User.remove_item(user_id, currency, amount, reason='tax')
        await Logs.add('tax_paid', user_id=user_id,
                                   currency=currency,
                                   amount=amount)

    # ---------- private -------------
    @staticmethod
    @aiocache.cached(ttl=86400)
    async def build_pig(skins: tuple, genetic: tuple = None, eye_emotion: str = None,
                        remove_transparency: bool = True, context: str = None):
        """The actual code is hidden due to security reasons

        context picks which art the same skins are drawn with - a community pig is a
        different shape from a personal one, so its items have their own aligned images.
        """
        if context == 'server':
            if genetic is None:
                genetic = tuple(config.default_guild_pig['genetic'].items())
            skins = tuple((slot, None if slot in config.guild_pig_hidden_slots else item)
                          for slot, item in skins)
            genetic = tuple((slot, item) for slot, item in genetic
                            if slot not in config.guild_pig_hidden_slots)
        if config.github_version:
            return await Func.get_image_path_from_link(config.image_links['image_is_blocked'])
        else:
            from .hidden import Hidden
            return await Hidden.build_pig(skins, genetic, eye_emotion, remove_transparency, context)

    @staticmethod
    async def get_user_tax_percent(user_id, currency: str):
        """The actual code is hidden due to security reasons"""
        if config.github_version:
            return 5
        else:
            from .hidden import Hidden
            return Hidden.get_user_tax_percent(user_id, currency, await GameFunc.get_user_wealth(user_id))

    @staticmethod
    async def get_duel_winning_chances(user1_id: int, user2_id: int):
        """The actual code is hidden due to security reasons
        Well, actually not really, but whatever"""
        if config.github_version:
            return {user1_id: 50, user2_id: 50}
        else:
            from .hidden import Hidden
            return await Hidden.get_duel_winning_chances(user1_id, user2_id)

