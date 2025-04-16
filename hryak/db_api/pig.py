import json, random

from .connection import Connection
from ..functions import Func, translate
from ..locale import Locale
from .. import config
from .item import Item
from .history import History


class Pig:

    @staticmethod
    def fix_pig_structure_for_all_users(nested_key_path: str = '', standard_values: dict = None):
        if standard_values is None:
            standard_values = config.default_pig
        Connection.make_request(f"UPDATE {config.users_schema} SET pig = '{'{}'}' WHERE pig IS NULL")
        for k, v in standard_values.items():
            new_key_path = f"{nested_key_path}.{k}" if nested_key_path else k
            if type(v) in [dict]:
                Connection.make_request(f"""
                UPDATE {config.users_schema}
                SET pig = JSON_SET(pig, '$.{new_key_path}', CAST(%s AS JSON))
                WHERE JSON_EXTRACT(pig, '$.{new_key_path}') IS NULL;
                """, params=(json.dumps(v),))
                Pig.fix_pig_structure_for_all_users(new_key_path, standard_values[k])
            else:
                Connection.make_request(f"""
                UPDATE {config.users_schema}
                SET pig = JSON_SET(pig, '$.{new_key_path}', {'CAST(%s AS JSON)' if isinstance(v, list) else '%s'})
                WHERE JSON_EXTRACT(pig, '$.{new_key_path}') IS NULL;
                """, params=(json.dumps(v) if isinstance(v, list) else v,))

    @staticmethod
    def get(user_id) -> dict:
        if type(user_id) is not list:
            result = Connection.make_request(
                f"SELECT pig FROM {config.users_schema} WHERE id = %s",
                params=(user_id,),
                commit=False,
                fetch=True,
            )
            print(111, result)
            if result is not None:
                return json.loads(result)
            else:
                return {}
        else:
            user_ids = []
            for i in user_id:
                user_ids.append(int(i))
            result = Connection.make_request(
                f"SELECT pig FROM {config.users_schema} WHERE id IN {tuple(user_ids)}",
                commit=False,
                fetch=True,
                fetchall=True,
                fetch_first=False
            )
            if result is not None:
                final_result = {}
                for i, j in enumerate(result):
                    final_result[user_ids[i]] = json.loads(j[0])
                return final_result
            else:
                return {}

    @staticmethod
    def update_pig(user_id, new_pig):
        new_pig = json.dumps(new_pig, ensure_ascii=False)
        Connection.make_request(
            f"UPDATE {config.users_schema} SET pig = %s WHERE id = {user_id}", (new_pig,)
        )

    @staticmethod
    def set_buffs(user_id, new_buffs):
        pig = Pig.get(user_id)
        pig['buffs'] = new_buffs
        Pig.update_pig(user_id, pig)

    @staticmethod
    def get_buffs(user_id):
        pig = Pig.get(user_id)
        return pig['buffs']

    @staticmethod
    def add_buff(user_id, buff, amount):
        pig = Pig.get(user_id)
        if buff not in pig['buffs']:
            pig['buffs'][buff] = {}
        if buff == 'activated_charcoal':
            if 'expires' not in pig['buffs'][buff]:
                pig['buffs'][buff]['expires'] = 0
            if Pig.buff_expired(user_id, buff):
                pig['buffs'][buff]['expires'] = Func.generate_current_timestamp() + Item.get_buff_duration(buff)
            else:
                pig['buffs'][buff]['expires'] += Item.get_buff_duration(buff)
        else:
            if 'amount' not in pig['buffs'][buff]:
                pig['buffs'][buff]['amount'] = 0
            pig['buffs'][buff]['amount'] += amount
        Pig.update_pig(user_id, pig)

    @staticmethod
    def buff_expired(user_id, buff):
        return Func.generate_current_timestamp() > Pig.get_buff_expiration_timestamp(user_id, buff)

    @staticmethod
    def remove_buff(user_id, buff, amount: int = 1):
        pig = Pig.get(user_id)
        if buff == 'activated_charcoal':
            return
        else:
            if buff in pig['buffs'] and pig['buffs'][buff]['amount'] > 0:
                pig['buffs'][buff]['amount'] -= amount
        Pig.update_pig(user_id, pig)

    @staticmethod
    def get_buff_data(user_id, buff):
        pig = Pig.get(user_id)
        if buff in pig['buffs']:
            return pig['buffs'][buff]

    @staticmethod
    def get_buff_amount(user_id, buff):
        if Pig.get_buff_data(user_id, buff) is not None and 'amount' in Pig.get_buff_data(user_id, buff):
            return Pig.get_buff_data(user_id, buff)['amount']
        elif 'expires' in Pig.get_buff_data(user_id, buff):
            if not Pig.buff_expired(user_id, buff):
                return (Pig.get_buff_data(user_id, buff)['expires'] - Func.generate_current_timestamp()) // Item.get_buff_duration(buff) + 1
        return 0

    @staticmethod
    def get_buff_expiration_timestamp(user_id, buff):
        if Pig.get_buff_data(user_id, buff) is not None and 'expires' in Pig.get_buff_data(user_id, buff):
            return Pig.get_buff_data(user_id, buff)['expires']
        return 0

    @staticmethod
    def get_buff_name(buff, lang):
        if Item.exists(buff):
            return Item.get_name(buff, lang)
        else:
            return translate(Locale.BuffsNames[buff], lang)

    @staticmethod
    def create(user_id, name: str = None):
        pig = config.default_pig.copy()
        pig['genetic']['body'] = random.choice(config.default_pig_body_genetic)
        pig['genetic']['eyes'] = random.choice(config.default_pig_eyes_genetic)
        pig['genetic']['pupils'] = random.choice(config.default_pig_pupils_genetic)
        if name is None:
            pig['name'] = random.choice(config.pig_names)
        else:
            pig['name'] = name
        Pig.update_pig(user_id, pig)

    @staticmethod
    def rename(user_id, name: str):
        pig = Pig.get(user_id)
        pig['name'] = name
        Pig.update_pig(user_id, pig)

    @staticmethod
    def set_genetic(user_id, key, value):
        pig = Pig.get(user_id)
        pig['genetic'][key] = value
        Pig.update_pig(user_id, pig)

    @staticmethod
    def get_genetic(user_id, key):
        pig = Pig.get(user_id)
        if key == 'all':
            return pig['genetic']
        if key in pig['genetic']:
            return pig['genetic'][key]

    @staticmethod
    def get_name(user_id):
        pig = Pig.get(user_id)
        return pig['name']

    @staticmethod
    def set_skin(user_id, item_id, layer=None):
        pig = Pig.get(user_id)
        pig['skins'] = Pig.set_skin_to_options(pig['skins'], item_id, layer)
        Pig.update_pig(user_id, pig)

    @staticmethod
    def set_skin_to_options(skins, item_id, layer=None):
        skins = skins.copy()
        if layer is None:
            for layer in Item.get_skin_layers(item_id):
                if layer in config.default_pig['skins']:
                    skins[layer] = item_id
            skins[Item.get_skin_type(item_id)] = item_id
        else:
            skins[layer] = item_id
        return skins

    @staticmethod
    def remove_skin(user_id, item_id, layer=None):
        pig = Pig.get(user_id)
        pig['skins'] = Pig.remove_skin_from_options(pig['skins'], item_id, layer)
        Pig.update_pig(user_id, pig)

    @staticmethod
    def remove_skin_from_options(skins, item_id, layer=None):
        if layer is None:
            for layer in Item.get_skin_layers(item_id):
                if layer in config.default_pig['skins'] and skins[layer] == item_id:
                    skins[layer] = None
            if skins.get(Item.get_skin_type(item_id)) == item_id:
                skins[Item.get_skin_type(item_id)] = None
        else:
            skins[layer] = None
        return skins

    @staticmethod
    def get_skin(user_id, key):
        pig = Pig.get(user_id)
        if key == 'all':
            return pig['skins']
        if key in pig['skins']:
            return pig['skins'][key]


    @staticmethod
    def get_time_to_next_feed(user_id):
        last_feed = History.get_last_feed(user_id)
        if last_feed is None:
            return -1
        print(123434, config.pig_feed_cooldown)
        next_feed = last_feed + config.pig_feed_cooldown - Func.generate_current_timestamp()
        return next_feed if next_feed > 0 else -1

    @staticmethod
    def get_time_of_next_feed(user_id):
        if Pig.get_time_to_next_feed(user_id) == -1:
            return Func.generate_current_timestamp()
        return Func.generate_current_timestamp() + Pig.get_time_to_next_feed(user_id)

    @staticmethod
    def is_ready_to_feed(user_id):
        if History.get_last_feed(user_id) is not None:
            if Func.generate_current_timestamp() < Pig.get_time_of_next_feed(user_id):
                return False
        return True

    @staticmethod
    def is_ready_to_butcher(user_id):
        if History.get_last_butcher(user_id) is not None:
            if Func.generate_current_timestamp() < Pig.get_time_of_next_butcher(user_id):
                return False
        return True

    @staticmethod
    def get_time_to_next_butcher(user_id):
        last_butcher = History.get_last_butcher(user_id)
        if last_butcher is None:
            return -1
        next_butcher = last_butcher + config.pig_butcher_cooldown - Func.generate_current_timestamp()
        return next_butcher if next_butcher > 0 else -1

    @staticmethod
    def get_time_of_next_butcher(user_id):
        if Pig.get_time_to_next_butcher(user_id) == -1:
            return Func.generate_current_timestamp()
        return Func.generate_current_timestamp() + Pig.get_time_to_next_butcher(user_id)

    @staticmethod
    def add_weight(user_id, weight: float):
        pig = Pig.get(user_id)
        pig['weight'] += weight
        pig['weight'] = round(pig['weight'], 1)
        if pig['weight'] <= .1:
            pig['weight'] = .1
        Pig.update_pig(user_id, pig)

    @staticmethod
    def get_weight(user_id):
        if type(user_id) != list:
            pig = Pig.get(user_id)
            return pig['weight']
        else:
            weight = 0
            pigs = Pig.get(user_id)
            for pig in pigs.values():
                weight += pig['weight']
            return weight

    @staticmethod
    def age(user_id, lang=None):
        weight = Pig.get_weight(user_id)
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

