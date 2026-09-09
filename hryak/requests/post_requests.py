import math
import random

from hryak.db_api import *
from hryak.functions import Func
from hryak.game_functions import GameFunc
from hryak import config
from hryak.statuses import Status

async def feed(user_id: int, client = None):
    ready_to_feed = await Pig.is_ready_to_feed(user_id)
    if not ready_to_feed:
        return {'status': Status.NOT_READY, 'try_again': await Pig.get_time_of_next_feed(user_id)}
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
    if pooped_amount:
        # a vomit poops nothing, and adding zero is not free: every inventory write is a
        # write of the whole blob, so a no-op one can only ever lose somebody else's
        await User.add_item(user_id, 'poop', pooped_amount, reason='feed')
    await History.add_feed_to_history(user_id, Func.generate_current_timestamp())
    # the reminder has served its purpose, so the next cooldown can raise a fresh one
    await Stats.set_notification_sent(user_id, 'feed_reminder', False)
    if Func.generate_current_timestamp() - await History.get_last_streak_timestamp(user_id) >= config.streak_timeout:
        await Stats.add_streak(user_id)
        await History.add_streak_to_history(user_id, Func.generate_current_timestamp(), 'feed')
    return {"status": Status.SUCCESS, "weight_added": weight_add, "pooped_amount": pooped_amount, "vomit": vomit}


async def butcher(user_id: int):
    ready_to_butcher = await Pig.is_ready_to_butcher(user_id)
    if not ready_to_butcher:
        return {'status': Status.NOT_READY, 'try_again': await Pig.get_time_of_next_butcher(user_id)}
    if await Item.get_amount('knife', user_id) <= 0:
        return {'status': Status.NO_ITEM_KNIFE}
    lard_add = random.randrange(4, 8)
    await User.add_item(user_id, 'lard', lard_add, reason='butcher')
    weight_lost = round(random.uniform(.2, .7) * lard_add, 1)
    await Pig.add_weight(user_id, -weight_lost)
    await History.add_butcher_to_history(user_id, Func.generate_current_timestamp())
    # the reminder has served its purpose, so the next cooldown can raise a fresh one
    await Stats.set_notification_sent(user_id, 'butcher_reminder', False)
    return {"status": Status.SUCCESS, "lard_added": lard_add, "weight_lost": weight_lost}

async def rename(user_id: int, name: str):
    await Pig.rename(user_id, name)
    for i in config.illegal_name_symbols:
        name = name.replace(i, '')
    if not name:
        name = 'Hryak'
    await Pig.rename(user_id, name)
    return {"status": Status.SUCCESS}

async def use_promocode(user_id: int, code: str):
    if not await PromoCode.exists(code):
        return {'status': Status.NOT_EXIST}
    if await PromoCode.used_times(code) >= await PromoCode.max_uses(code):
        return {'status': Status.USED_TOO_MANY_TIMES}
    if await PromoCode.created(code) + await PromoCode.expires_in(code) < Func.generate_current_timestamp() and await PromoCode.expires_in(code) != -1:
        return {'status': Status.EXPIRED}
    if await PromoCode.get_user_used_times(code, user_id) > 0:
        return {'status': Status.ALREADY_USED}
    rewards = await PromoCode.get_rewards(code)
    for item in rewards:
        if item == 'weight':
            await Pig.add_weight(user_id, rewards[item])
        else:
            await User.add_item(user_id, item, rewards[item], reason='promocode')
    await PromoCode.add_users_used(code, user_id)
    return {"status": Status.SUCCESS, "rewards": rewards}

async def send_money(user_id: int, amount: int, currency: str, to_user=None, to_guild=None,
                     confirmed: bool = True):
    """Sends money to a person or to a server pig - fill whichever target slot applies,
    the same way User.transfer_item does."""
    if to_user is not None:
        await User.register_user_if_not_exists(to_user)
    amount = abs(amount)
    tax = await GameFunc.get_user_tax_percent(user_id, currency)
    amount_with_tax = await GameFunc.get_transfer_amount_with_tax(amount, tax)
    if amount_with_tax > await Item.get_amount(currency, user_id):
        return {'status': Status.NO_MONEY, "tax": tax, "amount_with_tax": amount_with_tax}
    if confirmed:
        await User.transfer_item(from_user=user_id, to_user=to_user, to_guild=to_guild,
                                 item_id=currency, amount=amount, reason='send_money')
        await GameFunc.pay_tax(user_id, amount_with_tax - amount, currency)
        return {"status": Status.SUCCESS, "tax": tax, "amount_with_tax": amount_with_tax}
    else:
        return {"status": Status.PENDING, "tax": tax, "amount_with_tax": amount_with_tax}

async def wear_skin(user_id: int, item_id: str, parts: list = None):
    not_compatible_skins = await GameFunc.get_not_compatible_active_skins(user_id, item_id)
    if not_compatible_skins:
        return {'status': Status.NOT_COMPATIBLE_SKINS, 'skins': not_compatible_skins}
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
            return {'status': Status.PENDING_CHOOSE_PARTS}
        else:
            await Pig.set_skin(user_id, item_id)
    return {'status': Status.SUCCESS}

async def skin_remove(user_id: int, item_id: str):
    await Pig.remove_skin(user_id, item_id)
    return {"status": Status.SUCCESS}

async def eat_poop(user_id: int, item_id: str):
    if await Item.get_amount(item_id, user_id) < 1:
        return {'status': Status.NOT_ENOUGH_ITEMS}
    await User.remove_item(user_id, item_id, reason='eat_poop')
    return {'status': Status.SUCCESS, 'scenario': random.choice(['poisoned', 'dizzy', 'question', 'dad'])}

async def pay_doctor(user_id: int):
    if await Item.get_amount('coins', user_id) < config.doctor_price:
        return {'status': Status.NO_MONEY}
    await User.remove_item(user_id, 'coins', config.doctor_price, reason='doctor')
    return {'status': Status.SUCCESS}

async def wrap_gift(user_id: int, contents: dict, wrapping_paper_id: str = 'wrapping_paper',
                    style: str = None, name: str = None, description: str = None):
    """Puts a pile of items into a gift, spending one wrapping paper.

    Everything happens in one transaction. The paper is spent, the contents leave the
    inventory and the gift appears in the same commit - half of this landing would either
    destroy the contents or hand out a free gift, and both are unrecoverable because the
    gift exists exactly once.

    The holdings are read back under a row lock rather than trusted from the caller: the
    person picked these items some seconds ago through several interactions, and may have
    spent them since.
    """
    contents = {i: (a.get('amount', 0) if isinstance(a, dict) else a)
                for i, a in (contents or {}).items()}
    contents = {i: round(a) for i, a in contents.items() if a and round(a) > 0}
    if not contents:
        return {'status': Status.NOTHING_TO_WRAP}

    # a gift may hold a gift, and the joke stops where valuing one stops being cheap
    for item_id in contents:
        if await GameFunc.get_container_depth(item_id) + 1 >= config.container_max_depth:
            return {'status': Status.WRAPPED_TOO_DEEP}

    gift_id = f'gift?i={await UniqueItem.generate_new_unique_id()}'
    data = {'contents': {i: {'amount': a} for i, a in contents.items()},
            'style': style, 'from': str(user_id)}
    if name:
        data['name'] = name
    if description:
        data['description'] = description

    async with Connection.transaction() as cur:
        inventory = await User.get_inventory_for_update(user_id, cur)

        if await Item.get_amount(wrapping_paper_id, inventory=inventory) < 1:
            return {'status': Status.NOT_ENOUGH_ITEMS, 'item_id': wrapping_paper_id}
        for item_id, amount in contents.items():
            if await Item.get_amount(item_id, inventory=inventory) < amount:
                return {'status': Status.NOT_ENOUGH_ITEMS, 'item_id': item_id}

        await User.change_item_amount(user_id, wrapping_paper_id, -1, cur=cur)
        for item_id, amount in contents.items():
            await User.change_item_amount(user_id, item_id, -amount, cur=cur)
        if not await UniqueItem.create(gift_id, data, cur=cur):
            return {'status': Status.NOT_EXIST}      # id collided; nothing committed
        await User.change_item_amount(user_id, gift_id, 1, cur=cur)

    await User.clear_get_inventory_cache(user_id)
    await Logs.add('gift_wrapped', user_id=user_id, item_id=gift_id,
                   items=len(contents), style=style)
    return {'status': Status.SUCCESS, 'item_id': gift_id, 'contents': contents}


async def send_gift(user_id: int, to_user_id: int, item_id: str):
    """Delivers a wrapped gift to somebody, charging the fee on what is inside.

    The fee comes from calculate_item_tax, which is the same question /trade asks of every
    item it moves - so wrapping something and trading it costs exactly what sending it
    does, and there is no cheaper door.

    Charged before the move, the way a trade does it. Neither order can lose the gift: it
    is only ever in one inventory or the other, and a failure after the fee leaves the
    sender out of pocket but still holding it.
    """
    if user_id == to_user_id:
        return {'status': Status.NOT_ALLOWED}
    if not await GameFunc.get_container_contents(item_id):
        return {'status': Status.NOT_A_CONTAINER}
    if await Item.get_amount(item_id, user_id) < 1:
        return {'status': Status.NOT_ENOUGH_ITEMS, 'item_id': item_id}

    fee, currency = await GameFunc.calculate_item_tax(item_id, user_id)
    fee = math.ceil(fee)
    if fee > 0 and await Item.get_amount(currency, user_id) < fee:
        return {'status': Status.NO_MONEY, 'fee': fee, 'currency': currency}

    await User.register_user_if_not_exists(to_user_id)

    if fee > 0:
        await GameFunc.pay_tax(user_id, fee, currency)
    if not await User.transfer_item(from_user=user_id, to_user=to_user_id,
                                    item_id=item_id, amount=1, reason='gift'):
        return {'status': Status.NOT_ENOUGH_ITEMS, 'item_id': item_id}
    return {'status': Status.SUCCESS, 'fee': fee, 'currency': currency}


async def unwrap_gift(user_id: int, item_id: str):
    """Opens a gift and hands its contents to whoever is holding it.

    Both the inventory entry and the record are destroyed - the wrapping is spent, which
    is what keeps paper a repeat purchase, and an opened gift is not a thing anybody needs
    to look at again. Unlike a mini-pig, whose row outlives it because its parents are
    part of somebody else's lineage.
    """
    contents = await GameFunc.get_container_contents(item_id)
    if not contents:
        return {'status': Status.NOT_A_CONTAINER}
    if await Item.get_amount(item_id, user_id) < 1:
        return {'status': Status.NOT_ENOUGH_ITEMS, 'item_id': item_id}

    dropped = {i: (a.get('amount', 0) if isinstance(a, dict) else a)
               for i, a in contents.items()}
    async with Connection.transaction() as cur:
        inventory = await User.get_inventory_for_update(user_id, cur)
        if await Item.get_amount(item_id, inventory=inventory) < 1:
            return {'status': Status.NOT_ENOUGH_ITEMS, 'item_id': item_id}
        await User.change_item_amount(user_id, item_id, -1, cur=cur)
        for content_id, amount in dropped.items():
            await User.change_item_amount(user_id, content_id, amount, cur=cur)

    await User.clear_get_inventory_cache(user_id)
    await UniqueItem.remove(item_id)
    await Logs.add('gift_opened', user_id=user_id, item_id=item_id, items=len(dropped))
    return {'status': Status.SUCCESS, 'items_dropped': dropped}


async def open_case(user_id: int, item_id: str):
    if await Item.get_amount(item_id, user_id) < 1:
        return {'status': Status.NOT_ENOUGH_ITEMS}
    items_dropped = await Item.generate_case_drop(item_id)
    items_dropped.pop(None, None)
    await User.remove_item(user_id, item_id, 1, reason='case_opened')
    for item, amount in items_dropped.items():
        await User.add_item(user_id, item, amount, reason='case_drop')
    return {'status': Status.SUCCESS, 'items_dropped': items_dropped}
