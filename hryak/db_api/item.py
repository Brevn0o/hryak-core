from .connection import Connection
from ..functions import *
from hryak import config
from ..locale import Locale
import aiofiles
import aiocache
import random
import json

class Item:
    @staticmethod
    async def get_props(item_id: str):
        if item_id is None or '.' not in item_id:
            return {}
        return {i.split('=')[0]: i.split('=')[1] for i in item_id.split('.')[1:]}

    @staticmethod
    async def clean_id(item_id: str):
        return item_id.split('.')[0] if item_id else None

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="item.get_data")
    async def get_data(item_id: str, key: str, context: str = None):
        """Reads a field off an item.

        Anything shared - name, emoji, rarity - sits at the top level. Everything that
        depends on whose pig it is lives in '<context>_config', so the same item can cost
        one thing for a person and another for a server. A server falls back to the
        individual config only for the keys in item_context_fallback_keys, which is how a
        skin with no server art of its own still renders.
        """
        clean_id = await Item.clean_id(item_id)
        item = config.items.get(clean_id)
        if item is None:
            return None
        item = config.item_in_context(item, context)
        if key not in item:
            return None
        res = item[key]
        return res.copy() if isinstance(res, (list, dict, set)) else res

    @staticmethod
    async def clear_get_data_cache(params: tuple = None):
        await Func.clear_db_cache('item.get_data', Item.get_data, params) if params else \
            await Func.clear_db_cache('item.get_data', Item.get_data)

    @staticmethod
    async def exists(item_id: str):
        return await Item.clean_id(item_id) in config.items

    @staticmethod
    async def get_name(item_id: str, lang: str = None):
        name = await Item.get_data(item_id, 'name')
        return translate(name, lang) if lang else name

    @staticmethod
    async def get_description(item_id: str, lang: str = None):
        description = await Item.get_data(item_id, 'description')
        return translate(description, lang) if lang else description

    @staticmethod
    async def get_type(item_id: str, lang: str = None):
        _type = await Item.get_data(item_id, 'type')
        return translate(Locale.ItemTypes[_type], lang) if lang else _type

    @staticmethod
    async def get_skin_config(item_id: str, context: str = None):
        data = await Item.get_data(item_id, 'skin_config', context)
        return data.copy() if data else {}

    @staticmethod
    async def get_skin_type(item_id: str, lang: str = None, context: str = None):
        """The slot a skin goes in, or None when it has no skin config in this context.

        An item can exist in one context and not the other - one sold only to servers has
        nothing in its individual config - and a list that asks the wrong way round would
        otherwise fail whole, since one bad lookup takes the entire embed with it.
        """
        # not named `config`: that would shadow the module the rest of this file relies on
        skin_config = await Item.get_skin_config(item_id, context)
        value = skin_config.get('type')
        if value is None:
            return None
        return translate(Locale.SkinTypes[value], lang) if lang else value

    @staticmethod
    async def get_not_compatible_skins(item_id: str, context: str = None):
        return (await Item.get_skin_config(item_id, context)).get('not_compatible_with', []).copy()

    @staticmethod
    async def get_skins_to_hide(item_id: str, context: str = None):
        return (await Item.get_skin_config(item_id, context)).get('hide', []).copy()

    @staticmethod
    async def get_skin_layers(item_id: str, context: str = None):
        return (await Item.get_skin_config(item_id, context)).get('layers', {}).copy()

    @staticmethod
    async def get_skin_layer(item_id: str, layer, context: str = None):
        return (await Item.get_skin_layers(item_id, context)).get(layer)

    @staticmethod
    async def get_skin_layer_image_path(item_id: str, layer: str, type_: str = 'image', context: str = None):
        layer_data = await Item.get_skin_layer(item_id, layer, context)
        image = layer_data.get(type_)
        return await Func.get_image_path_from_link(image) if isinstance(image, str) else image

    @staticmethod
    async def get_skin_layer_shadow(item_id: str, layer, context: str = None):
        return (await Item.get_skin_layer(item_id, layer, context)).get('shadow')

    @staticmethod
    async def get_skin_layer_before(item_id: str, layer, context: str = None):
        before = (await Item.get_skin_layer(item_id, layer, context)).get('before')
        return before.copy() if isinstance(before, list) else before

    @staticmethod
    async def get_skin_layer_after(item_id: str, layer, context: str = None):
        after = (await Item.get_skin_layer(item_id, layer, context)).get('after')
        return after.copy() if isinstance(after, list) else after

    @staticmethod
    async def get_skin_color(item_id: str, context: str = None):
        return (await Item.get_skin_config(item_id, context)).get('color')

    @staticmethod
    async def get_skin_group(item_id: str, context: str = None):
        return (await Item.get_skin_config(item_id, context)).get('item_group')

    @staticmethod
    async def get_skin_right_ear_line(item_id: str, type_: str, context: str = None):
        return (await Item.get_skin_config(item_id, context)).get(f'right_ear_line_{type_}')

    @staticmethod
    async def get_skin_right_ear_line_type(item_id: str, context: str = None):
        return (await Item.get_skin_config(item_id, context)).get('right_ear_line')

    @staticmethod
    async def get_skin_eyes_outline_hex_color(item_id: str, context: str = None):
        return (await Item.get_skin_config(item_id, context)).get('eyes_outline_hex_color')

    @staticmethod
    async def get_skin_right_eye_outline(item_id: str, context: str = None):
        return (await Item.get_skin_config(item_id, context)).get('right_eye_outline')

    @staticmethod
    async def get_skin_left_eye_outline(item_id: str, context: str = None):
        return (await Item.get_skin_config(item_id, context)).get('left_eye_outline')

    @staticmethod
    async def get_emoji(item_id: str):
        for _ in range(10):
            emoji = await Item.get_data(item_id, 'emoji')
            if emoji not in ['?', '?️']:
                return emoji
            await Item.clear_get_data_cache((item_id, 'emoji'))
        return '❓'

    @staticmethod
    async def get_inventory_type(item_id: str):
        return await Item.get_data(item_id, 'inventory_type')

    @staticmethod
    async def get_cases(item_id: str, context: str = None):
        return await Item.get_data(item_id, 'cases', context)

    @staticmethod
    async def get_rarity(item_id: str, lang: str = None):
        """Rarity is keyed by string everywhere - in the locale, in config.rarity_colors.

        Coerced rather than trusted: a single item typed as 3 instead of '3' used to take
        out every list it appeared in, since one bad lookup fails the whole embed.
        """
        rarity = await Item.get_data(item_id, 'rarity')
        if rarity is None:
            return None
        rarity = str(rarity)
        return translate(Locale.ItemRarities[rarity], lang) if lang else rarity

    @staticmethod
    async def _get_tax(item_id: str):
        return await Item.get_data(item_id, 'tax')

    @staticmethod
    async def get_wealth_impact(item_id: str, context: str = None):
        return await Item.get_data(item_id, 'wealth_impact', context)

    @staticmethod
    @aiocache.cached(ttl=86400)
    async def get_image_path(item_id: str, folder_path: str):
        path = Func.generate_temp_path('img', file_extension='png')
        if await Item.get_data(item_id, 'image') is not None:
            async with aiofiles.open(path, 'wb') as file:
                await file.write(open(await Item.get_data(item_id, 'image'), 'rb').read())
            return path

    @staticmethod
    async def get_cooked_item_id(item_id: str):
        return await Item.get_data(item_id, 'cooked_item_id')

    @staticmethod
    async def get_market_price(item_id: str, context: str = None):
        props = await Item.get_props(item_id)
        if props and 'p' in props:
            return int(props['p'])
        return await Item.get_data(item_id, 'market_price', context)

    @staticmethod
    async def get_market_price_currency(item_id: str, context: str = None):
        props = await Item.get_props(item_id)
        if props and 'c' in props:
            return props['c']
        return await Item.get_data(item_id, 'market_price_currency', context)

    @staticmethod
    async def get_shop_category(item_id: str, context: str = None):
        return await Item.get_data(item_id, 'shop_category', context)

    @staticmethod
    async def get_shop_cooldown(item_id: str):
        result = await Item.get_data(item_id, 'shop_cooldown')
        if result is not None:
            return int(list(result.keys())[0]), int(list(result.values())[0])
        return None, None

    @staticmethod
    async def get_buffs(item_id: str, context: str = None):
        return await Item.get_data(item_id, 'buffs', context)

    @staticmethod
    async def get_buff_duration(item_id: str, context: str = None):
        return await Item.get_data(item_id, 'buff_duration', context)

    @staticmethod
    async def get_case_drops(item_id: str, context: str = None):
        return await Item.get_data(item_id, 'case_drops', context)

    @staticmethod
    async def generate_case_drop(item_id: str):
        items_dropped = {}
        case_possible_drops = await Item.get_case_drops(item_id)
        for n, i in enumerate(case_possible_drops):
            if i == ['AUTO-ITEMS']:
                if item_id == 'common_case':
                    case_possible_drops[n] = [{"items": [], "amount": [1, 1], "chance": 30},
                                              {"items": [], "amount": [1, 1], "chance": 68},
                                              {"items": [], "amount": [1, 1], "chance": 2},
                                              {"items": [], "amount": [1, 1], "chance": 0.1}]
                    rarities = {'2': 0, '3': 1, '4': 2, '5': 3}
                    for j in config.items:
                        cases = await Item.get_cases(j)
                        if item_id in cases:
                            if cases[item_id] is not None:
                                case_possible_drops[n].append({"items": [j], "amount": [1, 1], "chance": cases[item_id]})
                            elif await Item.get_rarity(j) in rarities:
                                case_possible_drops[n][rarities[await Item.get_rarity(j)]]['items'].append(j)
                elif item_id == 'rare_case':
                    case_possible_drops[n] = [{"items": [], "amount": [1, 1], "chance": 25},
                                              {"items": [], "amount": [1, 1], "chance": 73},
                                              {"items": [], "amount": [1, 1], "chance": 2}]
                    rarities = {'3': 0, '4': 1, '5': 2}
                    for j in config.items:
                        cases = await Item.get_cases(j)
                        if item_id in cases:
                            if cases[item_id] is not None:
                                case_possible_drops[n].append({"items": [j], "amount": [1, 1], "chance": cases[item_id]})
                            elif await Item.get_rarity(j) in rarities:
                                case_possible_drops[n][rarities[await Item.get_rarity(j)]]['items'].append(j)
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
    async def get_requirements(item_id: str, context: str = None):
        return await Item.get_data(item_id, 'requirements', context)

    @staticmethod
    async def get_all_allowed_users_by_requirements(discord_client, item_id: str):
        requirements = await Item.get_requirements(item_id)
        requirements_results = []
        for n, i in enumerate(requirements):
            requirements_results.append([])
            for j in i:
                if 'guild' in j:
                    guild = discord_client.get_guild(j['guild'])
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
    async def is_user_allowed_by_item_requirements(discord_client, user_id: int, item_id: str):
        requirements = await Item.get_requirements(item_id)
        requirements_results = []
        for n, i in enumerate(requirements):
            requirements_results.append([])
            for j in i:
                if 'guild' in j:
                    guild = discord_client.get_guild(j['guild'])
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
    async def is_salable(item_id: str, context: str = None):
        return await Item.get_data(item_id, 'salable', context)

    @staticmethod
    async def get_sell_price(item_id: str, context: str = None):
        return await Item.get_data(item_id, 'sell_price', context)

    @staticmethod
    async def get_sell_price_currency(item_id: str, context: str = None):
        return await Item.get_data(item_id, 'sell_price_currency', context)

    @staticmethod
    async def is_tradable(item_id: str, context: str = None):
        return await Item.get_data(item_id, 'tradable', context)

    @staticmethod
    async def get_amount(item_id: str, user_id: int = None, inventory: dict = None):
        props = await Item.get_props(item_id)
        if props:
            return int(props['a'])
        if inventory is None and user_id is not None:
            from .user import User
            inventory = await User.get_inventory(user_id)
        if inventory is not None:
            return int(float(inventory.get(item_id, {}).get('amount', 0)))
        return 0
