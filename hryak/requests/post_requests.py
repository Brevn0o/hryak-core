import random

from hryak.db_api import *
from hryak.functions import Func
from hryak.game_functions import GameFunc
from hryak import config

def feed(user_id: int, client = None):
    ready_to_feed = Pig.is_ready_to_feed(user_id)
    if not ready_to_feed:
        return {'status': '400;not_ready', 'try_again': Pig.get_time_of_next_feed(user_id)}
    Stats.add_pig_fed(user_id, 1)
    buffs_to_give = GameFunc.calculate_buff_multipliers(user_id, use_buffs=True, client=client)

    add_weight_chances = {'add': 100 - buffs_to_give['vomit_chance'] * 100,
                          'remove': buffs_to_give['vomit_chance'] * 100}
    vomit = Func.random_choice_with_probability(add_weight_chances) == 'remove'

    pooped_amount = 0
    if not vomit:
        weight_add = random.uniform(1, 10)
        weight_add *= buffs_to_give['weight']

        pooped_amount = random.uniform(5, 15)
        pooped_amount *= buffs_to_give['pooping']
    else:
        weight_add = random.uniform(-5, -1)
    if pooped_amount < 0:
        pooped_amount = 0

    weight_add = round(weight_add, 1)
    pooped_amount = round(pooped_amount)

    Pig.add_weight(user_id, weight_add)
    User.add_item(user_id, 'poop', pooped_amount)
    History.add_feed_to_history(user_id, Func.generate_current_timestamp())
    if Func.generate_current_timestamp() - History.get_last_streak_timestamp(user_id) >= config.streak_timeout:
        Stats.add_streak(user_id)
        History.add_streak_to_history(user_id, Func.generate_current_timestamp(), 'feed')
    return {"status": 'success', "weight_added": weight_add, "pooped_amount": pooped_amount, "vomit": vomit}

def butcher(user_id: int):
    ready_to_butcher = Pig.is_ready_to_butcher(user_id)
    if not ready_to_butcher:
        return {'status': '400;not_ready', 'try_again': Pig.get_time_of_next_butcher(user_id)}
    if Item.get_amount('knife', user_id) <= 0:
        return {'status': '400;no_item;knife'}
    lard_add = random.randrange(8, 16)
    User.add_item(user_id, 'lard', lard_add)
    weight_lost = round(random.uniform(.2, .7) * lard_add, 1)
    Pig.add_weight(user_id, -weight_lost)
    History.add_butcher_to_history(user_id, Func.generate_current_timestamp())
    return {"status": 'success', "lard_added": lard_add, "weight_lost": weight_lost}

def rename(user_id: int, name: str):
    Pig.rename(user_id, name)
    for i in ['*', '`']:
        name = name.replace(i, '')
    if not name:
        name = 'Hryak'
    Pig.rename(user_id, name)
    return {"status": 'success'}