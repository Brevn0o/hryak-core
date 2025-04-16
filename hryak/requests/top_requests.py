from hryak.db_api import *
from hryak.functions import Func, translate
from hryak.game_functions import GameFunc
from hryak import config
from hryak.locale import Locale

def top_weight_users(lang: str):
    """
    Get the top users by weight.
    :return: list of tuples (user_id, weight, unit)
    """
    r = Connection.make_request(
        f"SELECT user_id, weight FROM {config.users_schema} ORDER BY JSON_UNQUOTE(JSON_EXTRACT(pig, $.weight)) DESC LIMIT 10",
        commit=False,
        fetch=True
    )
    result = []
    for user_id, weight in r:
        result.append((user_id, weight, translate(Locale.Global.kg, lang)))
    return {'status': 'success', 'result': result}

def top_amount_of_items_users(item_id):
    """
    Get the top users by amount of item.
    :return: list of tuples (user_id, amount, unit)
    """
    r = Connection.make_request(
        f"SELECT user_id, amount FROM {config.users_schema} ORDER BY JSON_UNQUOTE(JSON_EXTRACT(inventory, CONCAT('$.', %s, '.amount'))) DESC LIMIT 10",
        params=(item_id,),
        commit=False,
        fetch=True
    )
    result = []
    for user_id, amount in r:
        result.append((user_id, amount, Item.get_emoji(item_id)))
    return {'status': 'success', 'result': result}

def top_streak_users():
    """
    Get the top users by streak.
    :return: list of tuples (user_id, streak, unit)
    """
    r = Connection.make_request(
        f"SELECT user_id, streak FROM {config.users_schema} ORDER BY JSON_UNQUOTE(JSON_EXTRACT(stats, '$.streak')) DESC LIMIT 10",
        commit=False,
        fetch=True
    )
    result = []
    for user_id, streak in r:
        result.append((user_id, streak, '🔥'))
    return {'status': 'success', 'result': result}