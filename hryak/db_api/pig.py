import json, random

import aiocache
from cachetools import cached

from .connection import Connection
from ..functions import Func, translate
from ..locale import Locale
from hryak import config
from .item import Item
from .history import History


class Pig:

    @staticmethod
    async def fix_pig_structure_for_all_users(nested_key_path: str = '', standard_values: dict = None):
        if standard_values is None:
            standard_values = config.default_pig
        await Connection.make_request(f"UPDATE {config.users_schema} SET pig = %s WHERE pig IS NULL",
                                params=(json.dumps({}),))
        for k, v in standard_values.items():
            new_key_path = f"{nested_key_path}.{k}" if nested_key_path else k
            if type(v) in [dict]:
                await Connection.make_request(f"""
                UPDATE {config.users_schema}
                SET pig = JSON_SET(pig, '$.{new_key_path}', CAST(%s AS JSON))
                WHERE JSON_EXTRACT(pig, '$.{new_key_path}') IS NULL;
                """, params=(json.dumps(v),))
                await Pig.fix_pig_structure_for_all_users(new_key_path, standard_values[k])
            else:
                await Connection.make_request(f"""
                UPDATE {config.users_schema}
                SET pig = JSON_SET(pig, '$.{new_key_path}', {'CAST(%s AS JSON)' if isinstance(v, list) else '%s'})
                WHERE JSON_EXTRACT(pig, '$.{new_key_path}') IS NULL;
                """, params=(json.dumps(v) if isinstance(v, list) else v,))

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="pig.get")
    async def get(user_id) -> dict:
        result = await Connection.make_request(
            f"SELECT pig FROM {config.users_schema} WHERE id = %s",
            params=(user_id,),
            commit=False,
            fetch=True,
        )
        if result is not None:
            return json.loads(result)
        else:
            return {}

    @staticmethod
    async def clear_get_pig_cache(user_id: int):
        await Func.clear_db_cache('pig.get', Pig.get, user_id)


    @staticmethod
    async def update_pig(user_id: int, new_pig: dict):
        new_pig = json.dumps(new_pig, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET pig = %s WHERE id = {user_id}", (new_pig,)
        )
        await Pig.clear_get_pig_cache(user_id)

    @staticmethod
    async def set_buffs(user_id, new_buffs):
        pig = await Pig.get(user_id)
        pig['buffs'] = new_buffs
        await Pig.update_pig(user_id, pig)

    @staticmethod
    async def get_buffs(user_id):
        pig = await Pig.get(user_id)
        return pig['buffs']

    @staticmethod
    async def add_buff(user_id, buff, amount):
        pig = await Pig.get(user_id)
        if buff not in pig['buffs']:
            pig['buffs'][buff] = {}
        if buff == 'activated_charcoal':
            if 'expires' not in pig['buffs'][buff]:
                pig['buffs'][buff]['expires'] = 0
            if await Pig.buff_expired(user_id, buff):
                pig['buffs'][buff]['expires'] = Func.generate_current_timestamp() + await Item.get_buff_duration(buff)
            else:
                pig['buffs'][buff]['expires'] += await Item.get_buff_duration(buff)
        else:
            if 'amount' not in pig['buffs'][buff]:
                pig['buffs'][buff]['amount'] = 0
            pig['buffs'][buff]['amount'] += amount
        await Pig.update_pig(user_id, pig)

    @staticmethod
    async def buff_expired(user_id, buff):
        return Func.generate_current_timestamp() > await Pig.get_buff_expiration_timestamp(user_id, buff)

    @staticmethod
    async def remove_buff(user_id, buff, amount: int = 1):
        pig = await Pig.get(user_id)
        if buff == 'activated_charcoal':
            return
        else:
            if buff in pig['buffs'] and pig['buffs'][buff]['amount'] > 0:
                pig['buffs'][buff]['amount'] -= amount
        await Pig.update_pig(user_id, pig)

    @staticmethod
    async def get_buff_data(user_id, buff):
        pig = await Pig.get(user_id)
        if buff in pig['buffs']:
            return pig['buffs'][buff]

    @staticmethod
    async def get_buff_amount(user_id, buff):
        buff_data = await Pig.get_buff_data(user_id, buff)
        if buff_data is not None and 'amount' in buff_data:
            return buff_data['amount']
        elif 'expires' in buff_data:
            if not await Pig.buff_expired(user_id, buff):
                return (buff_data['expires'] - Func.generate_current_timestamp()) // await Item.get_buff_duration(buff) + 1
        return 0

    @staticmethod
    async def get_buff_expiration_timestamp(user_id, buff):
        buff_data = await Pig.get_buff_data(user_id, buff)
        if await Pig.get_buff_data(user_id, buff) is not None and 'expires' in await Pig.get_buff_data(user_id, buff):
            return buff_data['expires']
        return 0

    @staticmethod
    async def get_buff_name(buff, lang):
        if await Item.exists(buff):
            return await Item.get_name(buff, lang)
        else:
            return translate(Locale.BuffsNames[buff], lang)

    @staticmethod
    async def create(user_id, name: str = None):
        pig = config.default_pig.copy()
        pig['genetic']['body'] = random.choice(config.default_pig_body_genetic)
        pig['genetic']['eyes'] = random.choice(config.default_pig_eyes_genetic)
        pig['genetic']['pupils'] = random.choice(config.default_pig_pupils_genetic)
        if name is None:
            pig['name'] = random.choice(config.pig_names)
        else:
            pig['name'] = name
        await Pig.update_pig(user_id, pig)

    @staticmethod
    async def rename(user_id, name: str):
        pig = await Pig.get(user_id)
        pig['name'] = name
        await Pig.update_pig(user_id, pig)

    @staticmethod
    async def set_genetic(user_id, key, value):
        pig = await Pig.get(user_id)
        pig['genetic'][key] = value
        await Pig.update_pig(user_id, pig)

    @staticmethod
    async def get_genetic(user_id, key):
        pig = await Pig.get(user_id)
        if key == 'all':
            return pig['genetic']
        if key in pig['genetic']:
            return pig['genetic'][key]

    @staticmethod
    async def get_name(user_id):
        pig = await Pig.get(user_id)
        return pig['name']

    @staticmethod
    async def set_skin(user_id, item_id, layer=None):
        pig = await Pig.get(user_id)
        pig['skins'] = await Pig.set_skin_to_options(pig['skins'], item_id, layer)
        await Pig.update_pig(user_id, pig)

    @staticmethod
    async def set_skin_to_options(skins, item_id, layer=None):
        skins = skins.copy()
        if layer is None:
            for layer in await Item.get_skin_layers(item_id):
                if layer in config.default_pig['skins']:
                    skins[layer] = item_id
            skins[await Item.get_skin_type(item_id)] = item_id
        else:
            skins[layer] = item_id
        return skins

    @staticmethod
    async def remove_skin(user_id, item_id, layer=None):
        pig = await Pig.get(user_id)
        pig['skins'] = await Pig.remove_skin_from_options(pig['skins'], item_id, layer)
        await Pig.update_pig(user_id, pig)

    @staticmethod
    async def remove_skin_from_options(skins, item_id, layer=None):
        if layer is None:
            for layer in await Item.get_skin_layers(item_id):
                if layer in config.default_pig['skins'] and skins[layer] == item_id:
                    skins[layer] = None
            if skins.get(await Item.get_skin_type(item_id)) == item_id:
                skins[await Item.get_skin_type(item_id)] = None
        else:
            skins[layer] = None
        return skins

    @staticmethod
    async def get_skin(user_id, key):
        pig = await Pig.get(user_id)
        if key == 'all':
            return pig['skins']
        if key in pig['skins']:
            return pig['skins'][key]


    @staticmethod
    async def get_time_to_next_feed(user_id):
        last_feed = await History.get_last_feed(user_id)
        if last_feed is None:
            return -1
        print(123434, config.pig_feed_cooldown)
        next_feed = last_feed + config.pig_feed_cooldown - Func.generate_current_timestamp()
        return next_feed if next_feed > 0 else -1

    @staticmethod
    async def get_time_of_next_feed(user_id):
        if await Pig.get_time_to_next_feed(user_id) == -1:
            return Func.generate_current_timestamp()
        return Func.generate_current_timestamp() + await Pig.get_time_to_next_feed(user_id)

    @staticmethod
    async def is_ready_to_feed(user_id):
        if await History.get_last_feed(user_id) is not None:
            if Func.generate_current_timestamp() < await Pig.get_time_of_next_feed(user_id):
                return False
        return True

    @staticmethod
    async def is_ready_to_butcher(user_id):
        if await History.get_last_butcher(user_id) is not None:
            if Func.generate_current_timestamp() < await Pig.get_time_of_next_butcher(user_id):
                return False
        return True

    @staticmethod
    async def get_time_to_next_butcher(user_id):
        last_butcher = await History.get_last_butcher(user_id)
        if last_butcher is None:
            return -1
        next_butcher = last_butcher + config.pig_butcher_cooldown - Func.generate_current_timestamp()
        return next_butcher if next_butcher > 0 else -1

    @staticmethod
    async def get_time_of_next_butcher(user_id):
        if await Pig.get_time_to_next_butcher(user_id) == -1:
            return Func.generate_current_timestamp()
        return Func.generate_current_timestamp() + await Pig.get_time_to_next_butcher(user_id)

    @staticmethod
    async def add_weight(user_id, weight: float):
        pig = await Pig.get(user_id)
        pig['weight'] += weight
        pig['weight'] = round(pig['weight'], 1)
        if pig['weight'] <= .1:
            pig['weight'] = .1
        await Pig.update_pig(user_id, pig)

    @staticmethod
    async def get_weight(user_id):
        if type(user_id) != list:
            pig = await Pig.get(user_id)
            return pig['weight']
        else:
            weight = 0
            pigs = await Pig.get(user_id)
            for pig in pigs.values():
                weight += pig['weight']
            return weight

    @staticmethod
    async def age(user_id, lang=None):
        weight = await Pig.get_weight(user_id)
        max_age = '1'
        for age in config.pig_ages:
            if weight >= age:
                max_age = config.pig_ages[age]
            else:
                break
        if lang is None:
            return max_age
        else:
            return translate(Locale.PigAges[max_age], lang)

