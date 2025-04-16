from cachetools import cached

from .connection import Connection
from ..functions import *
from hryak import config
from ..locale import Locale


class Item:

    @staticmethod
    def get_props(item_id: str):
        if item_id is None:
            return
        props = {}
        if len(item_id.split('.')) == 1:
            return
        for i in item_id.split('.')[1:]:
            props[i.split('=')[0]] = i.split('=')[1]
        return props

    @staticmethod
    def clean_id(item_id: str):
        if item_id is not None:
            return item_id.split('.')[0]

    @staticmethod
    @cached(config.db_caches['item.get_data'])
    def get_data(item_id: str, key: str):
        if Item.clean_id(item_id) not in config.items or key not in config.items[Item.clean_id(item_id)]:
            return
        res = config.items[Item.clean_id(item_id)][key]
        if type(res) in [list, dict, set]:
            return res.copy()
        return res

    @staticmethod
    def clear_get_data_cache(params: tuple = None):
        if params is not None:
            Func.clear_db_cache('item.get_data', params)
        else:
            Func.clear_db_cache('item.get_data')

    @staticmethod
    def exists(item_id: str):
        return Item.clean_id(item_id) in config.items

    @staticmethod
    def get_name(item_id: str, lang: str = None):
        name = Item.get_data(item_id, 'name')
        if lang is not None:
            name = translate(name, lang)
        return name

    @staticmethod
    def get_description(item_id: str, lang: str = None):
        description = Item.get_data(item_id, 'description')
        if lang is not None:
            description = translate(description, lang)
        return description

    @staticmethod
    def get_type(item_id: str, lang: str = None):
        _type = Item.get_data(item_id, 'type')
        if lang is not None:
            _type = translate(Locale.ItemTypes[_type], lang)
        return _type

    @staticmethod
    def get_skin_config(item_id: str):
        return Item.get_data(item_id, 'skin_config').copy()

    @staticmethod
    def get_skin_type(item_id: str, lang: str = None):
        skin_config = Item.get_skin_config(item_id)
        skin_type = skin_config['type']
        if lang is not None:
            skin_type = translate(Locale.SkinTypes[skin_type], lang)
        return skin_type

    @staticmethod
    def get_not_compatible_skins(item_id: str):
        skin_config = Item.get_skin_config(item_id)
        if 'not_compatible_with' in skin_config:
            return skin_config['not_compatible_with'].copy()
        return []

    @staticmethod
    def get_skins_to_hide(item_id: str):
        skin_config = Item.get_skin_config(item_id)
        if 'hide' in skin_config:
            return skin_config['hide'].copy()
        return []

    @staticmethod
    def get_skin_layers(item_id: str):
        skin_config = Item.get_skin_config(item_id)
        layers = skin_config['layers'].copy()
        return layers

    @staticmethod
    def get_skin_layer(item_id: str, layer):
        layers = Item.get_skin_layers(item_id)
        return layers[layer]

    @staticmethod
    async def get_skin_layer_image_path(item_id: str, layer: str, type_: str = 'image'):
        layer = Item.get_skin_layer(item_id, layer)
        image = layer[type_]
        if type(image) == str:
            image = await Func.get_image_path_from_link(image)
        return image

    @staticmethod
    def get_skin_layer_shadow(item_id: str, layer):
        layer = Item.get_skin_layer(item_id, layer)
        if 'shadow' in layer:
            return layer['shadow']

    @staticmethod
    def get_skin_layer_before(item_id: str, layer):
        layer = Item.get_skin_layer(item_id, layer)
        if 'before' in layer:
            if isinstance(layer['before'], list):
                return layer['before'].copy()
            else:
                return layer['before']

    @staticmethod
    def get_skin_layer_after(item_id: str, layer):
        layer = Item.get_skin_layer(item_id, layer)
        if 'after' in layer:
            if isinstance(layer['after'], list):
                return layer['after'].copy()
            else:
                return layer['after']

    @staticmethod
    def get_skin_color(item_id: str):
        skin_config = Item.get_skin_config(item_id)
        if 'color' in skin_config:
            return skin_config['color']

    @staticmethod
    def get_skin_group(item_id: str):
        skin_config = Item.get_skin_config(item_id)
        if 'item_group' in skin_config:
            return skin_config['item_group']

    @staticmethod
    def get_skin_right_ear_line(item_id: str, type_: str):
        skin_config = Item.get_skin_config(item_id)
        if f'right_ear_line_{type_}' in skin_config:
            return skin_config[f'right_ear_line_{type_}']

    @staticmethod
    def get_skin_right_ear_line_type(item_id: str):
        skin_config = Item.get_skin_config(item_id)
        if f'right_ear_line' in skin_config:
            return skin_config[f'right_ear_line']

    @staticmethod
    def get_skin_eyes_outline_hex_color(item_id: str):
        skin_config = Item.get_skin_config(item_id)
        if 'eyes_outline_hex_color' in skin_config:
            return skin_config['eyes_outline_hex_color']

    @staticmethod
    def get_skin_right_eye_outline(item_id: str):
        skin_config = Item.get_skin_config(item_id)
        if 'right_eye_outline' in skin_config:
            return skin_config['right_eye_outline']

    @staticmethod
    def get_skin_left_eye_outline(item_id: str):
        skin_config = Item.get_skin_config(item_id)
        if 'left_eye_outline' in skin_config:
            return skin_config['left_eye_outline']

    @staticmethod
    def get_emoji(item_id: str):
        for i in range(10):
            e = Item.get_data(item_id, 'emoji')
            if e not in ['?', '?️']:
                break
            else:
                Item.clear_get_data_cache((item_id, 'emoji'))
        else:
            e = '❓'
        return e

    @staticmethod
    def clear_get_emoji_cache():
        Func.clear_db_cache('item.get_data')

    @staticmethod
    def get_inventory_type(item_id: str):
        return Item.get_data(item_id, 'inventory_type')

    @staticmethod
    def get_cases(item_id: str):
        return Item.get_data(item_id, 'cases')

    @staticmethod
    def get_rarity(item_id: str, lang: str = None):
        rarity = Item.get_data(item_id, 'rarity')
        if lang is not None:
            rarity = translate(Locale.ItemRarities[rarity], lang)
        return rarity

    @staticmethod
    def _get_tax(item_id: str):
        return Item.get_data(item_id, 'tax')

    @staticmethod
    def get_wealth_impact(item_id: str):
        return Item.get_data(item_id, 'wealth_impact')

    @staticmethod
    @aiocache.cached(ttl=86400)
    async def get_image_path(item_id: str, folder_path: str):
        path = Func.generate_temp_path(folder_path, 'img', file_extension='png')
        if Item.get_data(item_id, 'image') is not None:
            async with aiofiles.open(path, 'wb') as file:
                await file.write(open(Item.get_data(item_id, 'image'), 'rb').read())
            return path

    @staticmethod
    def get_cooked_item_id(item_id: str):
        return Item.get_data(item_id, 'cooked_item_id')

    @staticmethod
    def get_market_price(item_id: str):
        if Item.get_props(item_id):
            return int(Item.get_props(item_id)['p'])
        return Item.get_data(item_id, 'market_price')

    @staticmethod
    def get_market_price_currency(item_id: str):
        if Item.get_props(item_id):
            return Item.get_props(item_id)['c']
        return Item.get_data(item_id, 'market_price_currency')

    @staticmethod
    def get_shop_category(item_id: str):
        return Item.get_data(item_id, 'shop_category')

    @staticmethod
    def get_shop_cooldown(item_id: str):
        result = Item.get_data(item_id, 'shop_cooldown')
        if result is not None:
            return int(list(result.keys())[0]), int(list(result.values())[0])
        return None, None

    @staticmethod
    def get_buffs(item_id: str):
        return Item.get_data(item_id, 'buffs')

    @staticmethod
    def get_buff_duration(item_id: str):
        return Item.get_data(item_id, 'buff_duration')

    @staticmethod
    def get_case_drops(item_id: str):
        return Item.get_data(item_id, 'case_drops')

    @staticmethod
    def generate_case_drop(item_id: str):
        items_dropped = {}
        case_possible_drops = Item.get_case_drops(item_id)
        for n, i in enumerate(case_possible_drops):
            if i == ['AUTO-ITEMS']:
                if item_id == 'common_case':
                    case_possible_drops[n] = [{"items": [], "amount": [1, 1], "chance": 30},
                                              {"items": [], "amount": [1, 1], "chance": 68},
                                              {"items": [], "amount": [1, 1], "chance": 2},
                                              {"items": [], "amount": [1, 1], "chance": 0.1}]
                    rarities = {'2': 0, '3': 1, '4': 2, '5': 3}
                    for j in config.items:
                        if item_id in Item.get_cases(j):
                            if Item.get_cases(j)[item_id] is not None:
                                case_possible_drops[n].append({"items": [j], "amount": [1, 1], "chance": Item.get_cases(j)[item_id]})
                            elif Item.get_rarity(j) in rarities:
                                case_possible_drops[n][rarities[Item.get_rarity(j)]]['items'].append(j)
                elif item_id == 'rare_case':
                    case_possible_drops[n] = [{"items": [], "amount": [1, 1], "chance": 25},
                                              {"items": [], "amount": [1, 1], "chance": 73},
                                              {"items": [], "amount": [1, 1], "chance": 2}]
                    rarities = {'3': 0, '4': 1, '5': 2}
                    for j in config.items:
                        if item_id in Item.get_cases(j):
                            if Item.get_cases(j)[item_id] is not None:
                                case_possible_drops[n].append({"items": [j], "amount": [1, 1], "chance": Item.get_cases(j)[item_id]})
                            elif Item.get_rarity(j) in rarities:
                                case_possible_drops[n][rarities[Item.get_rarity(j)]]['items'].append(j)
        for i in case_possible_drops:
            if len(i) == 1 and i[0]['chance'] < 100:
                i.append({'items': [None], 'amount': [1, 1], 'chance': 100 - i[0]['chance']})
            items_dict_dropped = i[Func.random_choice_with_probability({n: j['chance'] for n, j in enumerate(i)})]
            items_dropped[random.choice(items_dict_dropped['items'])] = random.randrange(
                items_dict_dropped['amount'][0],
                items_dict_dropped['amount'][1]) if \
                items_dict_dropped['amount'][0] != items_dict_dropped['amount'][1] else items_dict_dropped['amount'][0]
        return items_dropped

    @staticmethod
    def get_requirements(item_id: str):
        return Item.get_data(item_id, 'requirements')

    @staticmethod
    def get_all_allowed_users_by_requirements(client, item_id: str):
        requirements = Item.get_requirements(item_id)
        requirements_results = []
        for n, i in enumerate(requirements):
            requirements_results.append([])
            for j in i:
                if 'guild' in j:
                    guild = client.get_guild(j['guild'])
                    if guild is not None:
                        if 'role' in j:
                            role = guild.get_role(j['role'])
                            requirements_results[n] += [str(i.id) for i in role.members]
                        else:
                            requirements_results[n] += [str(i.id) for i in guild.members]
                if 'user' in j:
                    requirements_results[n].append(str(j['user']))
        return Func.common_elements(requirements_results)

    @staticmethod
    def is_user_allowed_by_item_requirements(client, user_id: int, item_id: str):
        requirements = Item.get_requirements(item_id)
        requirements_results = []
        for n, i in enumerate(requirements):
            requirements_results.append([])
            for j in i:
                if 'guild' in j:
                    guild = client.get_guild(j['guild'])
                    if guild is not None:
                        member = guild.get_member(int(user_id))
                        if 'role' in j:
                            role = guild.get_role(j['role'])
                            if member is not None and role.id in [i.id for i in member.roles]:
                                requirements_results[n].append(True)
                            else:
                                requirements_results[n].append(False)
                        else:
                            if member is not None:
                                requirements_results[n].append(True)
                            else:
                                requirements_results[n].append(False)
                    else:
                        requirements_results[n].append(False)
                if 'user' in j:
                    if int(user_id) == j['user']:
                        requirements_results[n].append(True)
                    else:
                        requirements_results[n].append(False)
        final_result = True
        for i in [any(j) for j in requirements_results]:
            if i is False:
                final_result = False
        return final_result

    @staticmethod
    def is_salable(item_id: str):
        return Item.get_data(item_id, 'salable')

    @staticmethod
    def get_sell_price(item_id: str):
        return Item.get_data(item_id, 'sell_price')

    @staticmethod
    def get_sell_price_currency(item_id: str):
        return Item.get_data(item_id, 'sell_price_currency')

    @staticmethod
    def is_tradable(item_id: str):
        return Item.get_data(item_id, 'tradable')

    @staticmethod
    def get_amount(item_id: str, user_id: int = None):
        if Item.get_props(item_id):
            return int(Item.get_props(item_id)['a'])
        if user_id is not None:
            query = f"SELECT JSON_UNQUOTE(JSON_EXTRACT(inventory, CONCAT('$.', %s, '.amount'))) AS amount FROM {config.users_schema} WHERE id = %s"
            amount = Connection.make_request(query, params=(item_id, user_id,), commit=False, fetch=True)
            print(type(amount), amount)
            return int(amount)
        return 0
