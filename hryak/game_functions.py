import numpy as np
from scipy.interpolate import PchipInterpolator

from . import config
from .db_api import Pig, Item


class GameFunc:

    @staticmethod
    def calculate_buff_multipliers(user_id, use_buffs: bool = False, client=None):
        res = config.base_buff_multipliers.copy()
        pig_buffs = GameFunc.get_all_pig_buffs(client, user_id)
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
