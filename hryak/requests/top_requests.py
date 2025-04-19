from hryak.db_api import *
from hryak.functions import Func, translate
from hryak.game_functions import GameFunc
from hryak import config
from hryak.locale import Locale


async def __top_users(user_id: int, extra_select: str, order_by: str, where: str, units: str, guild=None):
    r = await Tech.get_all_users(extra_select=extra_select, order_by=order_by, where=where, limit=10, guild=guild)
    top_users = []
    print(r)
    for i, weight in r:
        top_users.append((i, weight, units))
    user_position = await Tech.get_user_position(user_id, order_by=order_by, where=where, guild=guild)
    return {'status': 'success', 'users': top_users, 'user_position': user_position}

async def top_weight_users(user_id: int, lang: str, guild=None):
    """
    Get the top users by weight.
    :return: list of tuples (user_id, weight, unit) and user_position
    """
    extra_select = "IFNULL(JSON_UNQUOTE(JSON_EXTRACT(pig, '$.weight')), '0')"
    order_by = "JSON_UNQUOTE(JSON_EXTRACT(pig, '$.weight'))"
    where = "JSON_UNQUOTE(JSON_EXTRACT(settings, '$.top_participate')) = 'true'"
    return await __top_users(user_id, extra_select, order_by, where, translate(Locale.Global.kg, lang), guild=guild)

async def top_amount_of_items_users(user_id: int, item_id: str, guild=None):
    """
    Get the top users by amount of item.
    :return: list of tuples (user_id, amount, unit) and user_position
    """
    extra_select = f"IFNULL(JSON_UNQUOTE(JSON_EXTRACT(inventory, '$.{item_id}.amount')), '0')"
    order_by = f"JSON_UNQUOTE(JSON_EXTRACT(inventory, '$.{item_id}.amount'))"
    where = "JSON_UNQUOTE(JSON_EXTRACT(settings, '$.top_participate')) = 'true'"
    return await __top_users(user_id, extra_select, order_by, where, await Item.get_emoji(item_id), guild=guild)

async def top_streak_users(user_id: int, guild=None):
    """
    Get the top users by streak.
    :return: list of tuples (user_id, streak, unit) and user_position
    """
    extra_select = "IFNULL(JSON_UNQUOTE(JSON_EXTRACT(stats, '$.streak')), '0')"
    order_by = "JSON_UNQUOTE(JSON_EXTRACT(stats, '$.streak'))"
    where = "JSON_UNQUOTE(JSON_EXTRACT(settings, '$.top_participate')) = 'true'"
    return await __top_users(user_id, extra_select, order_by, where, '🔥', guild=guild)