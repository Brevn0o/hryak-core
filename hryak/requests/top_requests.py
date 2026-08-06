import aiocache

from hryak.db_api import *
from hryak.functions import Func, translate
from hryak.game_functions import GameFunc
from hryak import config
from hryak.locale import Locale
from hryak.statuses import Status


@aiocache.cached(cache=aiocache.SimpleMemoryCache, ttl=120)
async def __top_users(user_id: int, extra_select: str, order_by: str, where: str, units: str, guild=None):
    r = await Tech.get_all_users(extra_select=extra_select, order_by=order_by, where=where, limit=10, guild=guild)
    top_users = []
    for i, weight in r:
        top_users.append((i, weight, units))
    user_position = await Tech.get_user_position(user_id, order_by=order_by, where=where, guild=guild)
    return {'status': Status.SUCCESS, 'users': top_users, 'user_position': user_position}

@aiocache.cached(cache=aiocache.SimpleMemoryCache, ttl=120)
async def __top_guilds(guild_id, extra_select: str, order_by: str, where: str, units: str, limit: int = 10):
    query = f'SELECT id, {extra_select} FROM {config.guilds_schema}'
    if where is not None:
        query += f' WHERE {where}'
    if order_by is not None:
        query += f' ORDER BY {order_by}'
    r = await Connection.make_request(query, commit=False, fetch=True, fetchall=True)
    if r is None:
        r = []
    top_guilds = []
    for i, value in r[:limit]:
        top_guilds.append((i, value, units))
    guild_ids = [i[0] for i in r]
    guild_position = guild_ids.index(str(guild_id)) if str(guild_id) in guild_ids else None
    return {'status': Status.SUCCESS, 'guilds': top_guilds, 'guild_position': guild_position}

async def top_weight_guilds(guild_id, lang: str):
    """
    Get the top guilds by the weight of their server pig.
    :return: list of tuples (guild_id, weight, unit) and guild_position
    """
    extra_select = "IFNULL(JSON_UNQUOTE(JSON_EXTRACT(pig, '$.weight')), '0')"
    order_by = "CAST(JSON_UNQUOTE(JSON_EXTRACT(pig, '$.weight')) AS DECIMAL(15,4)) DESC"
    where = "JSON_TYPE(JSON_EXTRACT(pig, '$.channel_id')) NOT IN ('NULL')"
    return await __top_guilds(guild_id, extra_select, order_by, where, translate(Locale.Global.kg, lang))

async def top_money_guilds(guild_id, lang: str, currency: str = 'coins'):
    """
    Get the top guilds by what their community pig has in the bank.
    :return: list of tuples (guild_id, amount, unit) and guild_position
    """
    amount = f"JSON_UNQUOTE(JSON_EXTRACT(pig, '$.inventory.{currency}.amount'))"
    extra_select = f"IFNULL({amount}, '0')"
    order_by = f"CAST(IFNULL({amount}, '0') AS DECIMAL(20,4)) DESC"
    where = "JSON_TYPE(JSON_EXTRACT(pig, '$.channel_id')) NOT IN ('NULL')"
    return await __top_guilds(guild_id, extra_select, order_by, where,
                              await Item.get_emoji(currency))


async def top_weight_users(user_id: int, lang: str, guild=None):
    """
    Get the top users by weight.
    :return: list of tuples (user_id, weight, unit) and user_position
    """
    extra_select = "IFNULL(JSON_UNQUOTE(JSON_EXTRACT(pig, '$.weight')), '0')"
    order_by = "CAST(JSON_UNQUOTE(JSON_EXTRACT(pig, '$.weight')) AS DECIMAL(15,4)) DESC"
    where = "JSON_UNQUOTE(JSON_EXTRACT(settings, '$.top_participate')) = 'true'"
    return await __top_users(user_id, extra_select, order_by, where, translate(Locale.Global.kg, lang), guild=guild)

async def top_amount_of_items_users(user_id: int, item_id: str, guild=None):
    """
    Get the top users by amount of item.
    :return: list of tuples (user_id, amount, unit) and user_position
    """
    extra_select = f"IFNULL(JSON_UNQUOTE(JSON_EXTRACT(inventory, '$.{item_id}.amount')), '0')"
    order_by = f"CAST(JSON_UNQUOTE(JSON_EXTRACT(inventory, '$.{item_id}.amount')) AS DECIMAL(15,4)) DESC"
    where = "JSON_UNQUOTE(JSON_EXTRACT(settings, '$.top_participate')) = 'true'"
    return await __top_users(user_id, extra_select, order_by, where, await Item.get_emoji(item_id), guild=guild)

async def top_streak_users(user_id: int, guild=None):
    """
    Get the top users by streak.
    :return: list of tuples (user_id, streak, unit) and user_position
    """
    extra_select = "IFNULL(JSON_UNQUOTE(JSON_EXTRACT(stats, '$.streak')), '0')"
    order_by = "CAST(JSON_UNQUOTE(JSON_EXTRACT(stats, '$.streak')) AS DECIMAL(15,4)) DESC"
    where = "JSON_UNQUOTE(JSON_EXTRACT(settings, '$.top_participate')) = 'true'"
    return await __top_users(user_id, extra_select, order_by, where, '🔥', guild=guild)