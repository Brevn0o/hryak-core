import math

import numpy as np
from scipy.interpolate import PchipInterpolator

from . import config
from .db_api import Pig, Item, User
from .hidden import Hidden


class GameFunc:

    @staticmethod
    def calculate_buff_multipliers(user_id, use_buffs: bool = False, client=None):
        res = config.base_buff_multipliers.copy()
        pig_buffs = GameFunc.get_all_pig_buffs(user_id, client)
        pig_buffs_raw = {i: [] for i in res.copy()}
        for buff in pig_buffs:
            if use_buffs and buff in ['laxative', 'compound_feed']:
                Pig.remove_buff(user_id, buff)
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
    def get_all_pig_buffs(user_id, client = None):
        buffs = {}
        for buff in Pig.get_buffs(user_id):
            if Pig.get_buff_amount(user_id, buff) > 0 or not Pig.buff_expired(user_id, buff):
                buffs[buff] = Item.get_buffs(buff)
            if client is not None:
                for i in config.BOT_GUILDS:
                    bot_guild = client.get_guild(i)
                    if bot_guild is not None:
                        if bot_guild.get_member(user_id) is not None:
                            buffs['support_server'] = {'weight': 'x1.05'}
        buffs['pig_weight'] = {}
        pchip_function = PchipInterpolator(np.array([0, 50, 100, 500, 5000, 20000, 1000000]),
                                           np.array([0, .5, 1, 5, 15, 20, 30]))
        buffs['pig_weight']['pooping'] = f'+{round(float(pchip_function(Pig.get_weight(user_id))), 2)}'
        pchip_function = PchipInterpolator(np.array([0, 20, 50, 1000, 10000, 1000000]),
                                           np.array([0, 0, 1, 1.5, 2, 10]))
        buffs['pig_weight']['vomit_chance'] = f'x{round(float(pchip_function(Pig.get_weight(user_id))), 2)}'
        return buffs

    @staticmethod
    def get_user_tax_percent(user_id, currency: str):
        """The actual code is hidden due to security reasons"""
        if config.github_version:
            return 5
        else:
            return Hidden.get_user_tax_percent(user_id, currency, GameFunc.get_user_wealth(user_id))

    @staticmethod
    def get_user_wealth(user_id):
        wealth = {}
        for item_id in User.get_inventory(user_id):
            if Item.get_wealth_impact(item_id) is not None and Item.get_market_price(item_id) is not None:
                if Item.get_market_price_currency(item_id) not in wealth:
                    wealth[Item.get_market_price_currency(item_id)] = 0
                wealth[Item.get_market_price_currency(item_id)] += Item.get_amount(item_id,
                                                                                   user_id) * Item.get_market_price(
                    item_id) * Item.get_wealth_impact(item_id)
        return wealth

    @staticmethod
    def calculate_item_tax(item_id, user_id):
        tax = Item._get_tax(item_id)
        if tax is None:
            return [0, "coins"]
        elif isinstance(tax, list):
            return tax
        elif tax == 'auto':
            return [round(Item.get_market_price(item_id) * (
                    GameFunc.get_user_tax_percent(user_id, Item.get_market_price_currency(item_id)) / 100), 3),
                    Item.get_market_price_currency(item_id)]
        elif tax.endswith('%'):
            return [round(Item.get_market_price(item_id) * (float(tax[:-1]) / 100), 3),
                    Item.get_market_price_currency(item_id)]

    @staticmethod
    def get_transfer_amount_with_tax(amount, tax):
        amount_with_tax = math.ceil(amount + amount * (tax / 100))
        return amount_with_tax
