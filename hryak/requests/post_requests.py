import random

from hryak.db_api import *
from hryak.functions import Func
from hryak.game_functions import GameFunc
from hryak import config

async def feed(user_id: int, client = None):
    ready_to_feed = await Pig.is_ready_to_feed(user_id)
    if not ready_to_feed:
        return {'status': '400;not_ready', 'try_again': await Pig.get_time_of_next_feed(user_id)}
    await Stats.add_pig_fed(user_id, 1)
    buffs_to_give = await GameFunc.calculate_buff_multipliers(user_id, use_buffs=True, client=client)

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

    await Pig.add_weight(user_id, weight_add)
    await User.add_item(user_id, 'poop', pooped_amount)
    await History.add_feed_to_history(user_id, Func.generate_current_timestamp())
    if Func.generate_current_timestamp() - await History.get_last_streak_timestamp(user_id) >= config.streak_timeout:
        await Stats.add_streak(user_id)
        await History.add_streak_to_history(user_id, Func.generate_current_timestamp(), 'feed')
    return {"status": 'success', "weight_added": weight_add, "pooped_amount": pooped_amount, "vomit": vomit}

async def butcher(user_id: int):
    ready_to_butcher = await Pig.is_ready_to_butcher(user_id)
    if not ready_to_butcher:
        return {'status': '400;not_ready', 'try_again': await Pig.get_time_of_next_butcher(user_id)}
    if await Item.get_amount('knife', user_id) <= 0:
        return {'status': '400;no_item;knife'}
    lard_add = random.randrange(8, 16)
    await User.add_item(user_id, 'lard', lard_add)
    weight_lost = round(random.uniform(.2, .7) * lard_add, 1)
    await Pig.add_weight(user_id, -weight_lost)
    await History.add_butcher_to_history(user_id, Func.generate_current_timestamp())
    return {"status": 'success', "lard_added": lard_add, "weight_lost": weight_lost}

async def rename(user_id: int, name: str):
    await Pig.rename(user_id, name)
    for i in ['*', '`']:
        name = name.replace(i, '')
    if not name:
        name = 'Hryak'
    await Pig.rename(user_id, name)
    return {"status": 'success'}

async def use_promocode(user_id: int, code: str):
    if not await PromoCode.exists(code):
        return {'status': '400;not_exist'}
    if await PromoCode.used_times(code) >= await PromoCode.max_uses(code):
        return {'status': '400;used_too_many_times'}
    if await PromoCode.created(code) + await PromoCode.expires_in(code) < Func.generate_current_timestamp() and await PromoCode.expires_in(code) != -1:
        return {'status': '400;expired'}
    if await PromoCode.get_user_used_times(code, user_id) > 0:
        return {'status': '400;already_used'}
    rewards = await PromoCode.get_rewards(code)
    for item in rewards:
        if item == 'weight':
            await Pig.add_weight(user_id, rewards[item])
        else:
            await User.add_item(user_id, item, rewards[item])
    await PromoCode.add_users_used(code, user_id)
    return {"status": 'success', "rewards": rewards}

async def send_money(user_id: int, receiver_id, amount: int, currency: str, confirmed: bool = True):
    await User.register_user_if_not_exists(receiver_id)
    amount = abs(amount)
    tax = await GameFunc.get_user_tax_percent(user_id, currency)
    amount_with_tax = await GameFunc.get_transfer_amount_with_tax(amount, tax)
    if amount_with_tax > await Item.get_amount(currency, user_id):
        return {'status': '400;no_money', "tax": tax, "amount_with_tax": amount_with_tax}
    if confirmed:
        await User.transfer_item(user_id, receiver_id, currency, amount)
        await User.remove_item(user_id, currency, amount_with_tax - amount)
        return {"status": 'success', "tax": tax, "amount_with_tax": amount_with_tax}
    else:
        return {"status": "pending", "tax": tax, "amount_with_tax": amount_with_tax}

async def wear_skin(user_id: int, item_id: str, parts: list = None):
    not_compatible_skins = await GameFunc.get_not_compatible_active_skins(user_id, item_id)
    if not_compatible_skins:
        return {'status': '400;not_compatible_skins', 'skins': not_compatible_skins}
    if parts is not None:
        if 'all' not in parts:
            for i in parts:
                await Pig.set_skin(user_id, item_id, i)
        else:
            await Pig.set_skin(user_id, item_id)
    else:
        choose_parts = False
        if await Item.get_skin_type(item_id) in ['eyes', 'pupils']:
            choose_parts = True
        if await Item.get_skin_type(item_id) in ['body'] and await Item.get_amount('body_combiner', user_id) > 0:
            choose_parts = True
        if choose_parts:
            return {'status': 'pending;choose_parts'}
        else:
            await Pig.set_skin(user_id, item_id)
    return {'status': 'success'}

async def skin_remove(user_id: int, item_id: str):
    await Pig.remove_skin(user_id, item_id)
    return {"status": 'success'}
