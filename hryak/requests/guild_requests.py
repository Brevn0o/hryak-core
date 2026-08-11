"""Everything a guild's shared pig can be asked to do.

Split out of post_requests because a server pig has a life of its own - it is fed, dressed,
voted on and paid out of, none of which a personal pig does. The rules that differ between
the two live here rather than being threaded through with flags.
"""
import random

from hryak.db_api import *
from hryak.functions import Func
from hryak.game_functions import GameFunc
from hryak import config
from hryak.statuses import Status


async def feed_guild_pig(user_id: int, guild_id: int):
    """One feed per user per cooldown across every server, so people have to pick a side.

    The cooldown comes off the user's own history - asking "when did this person last feed
    anyone's pig" of every guild's feed list would mean scanning the whole table.
    """
    if not await GuildPig.is_setup(guild_id):
        return {'status': Status.NOT_EXIST}
    next_feed = (await History.get_last_server_feed(user_id) or 0) + config.guild_pig_feed_cooldown
    if Func.generate_current_timestamp() < next_feed:
        return {'status': Status.NOT_READY, 'try_again': next_feed}
    weight_add = round(random.uniform(1, 10), 1)
    await GuildPig.add_feed(guild_id, user_id, weight_add)
    await History.add_server_feed_to_history(user_id, Func.generate_current_timestamp())
    return {'status': Status.SUCCESS,
            'weight_added': weight_add,
            'weight': await GuildPig.get_weight(guild_id),
            'try_again': Func.generate_current_timestamp() + config.guild_pig_feed_cooldown}


async def propose_server_purchase(user_id: int, guild_id: int, item_id: str, bypass: bool = False):
    """Checks whether this person may put a purchase to the server right now.

    It does not open anything - the front-end still has to create the poll and hand the
    message back through open_server_poll. Money is deliberately not checked here: the
    balance that matters is the one when the vote closes, a day later.
    """
    if not await GuildPig.is_setup(guild_id):
        return {'status': Status.NOT_EXIST}
    if not await Shop.is_item_in_shop(item_id, context='server'):
        return {'status': Status.NOT_EXIST}
    price = await Item.get_market_price(item_id)
    currency = await Item.get_market_price_currency(item_id)
    if bypass:  # whoever runs the server does not need anyone's permission
        return {'status': Status.SUCCESS, 'price': price, 'currency': currency, 'bypass': True}
    if not await GuildPig.get_polls_allowed(guild_id):
        return {'status': Status.NOT_ALLOWED}
    if await GuildPig.get_poll(guild_id, 'shop') is not None:
        return {'status': Status.IN_PROCESS}
    window = Func.generate_current_timestamp() - config.guild_pig_feeder_window
    if str(user_id) not in await GuildPig.get_feeders(guild_id, since=window):
        return {'status': Status.NOT_A_CONTRIBUTOR}
    next_proposal = await GuildPig.get_last_proposal(guild_id, user_id) + config.guild_pig_proposal_cooldown
    if Func.generate_current_timestamp() < next_proposal:
        return {'status': Status.NOT_READY, 'try_again': next_proposal}
    return {'status': Status.SUCCESS, 'price': price, 'currency': currency, 'bypass': False}


async def open_server_poll(user_id: int, guild_id: int, kind: str, message_id, data: dict = None):
    """Records a vote the front-end has just posted, and starts the proposer's cooldown.

    Whatever the vote is about travels in data and is handed straight back to the resolver,
    so a new kind of vote needs nothing here.
    """
    expires = Func.generate_current_timestamp() + config.guild_pig_poll_durations[kind]
    await GuildPig.set_poll(guild_id, kind, {**(data or {}),
                                             'message_id': str(message_id),
                                             'proposed_by': str(user_id),
                                             'expires': expires})
    await GuildPig.set_last_proposal(guild_id, user_id, Func.generate_current_timestamp())
    return {'status': Status.SUCCESS, 'expires': expires}


async def resolve_server_poll(guild_id: int, kind: str, yes: int, no: int):
    """Closes a finished vote and acts on it.

    The quorum is measured against the people who actually fed the pig this week, so a
    quiet server needs a handful of votes and a busy one needs proportionally more. What a
    passing vote then does is the only thing that differs between kinds.
    """
    poll = await GuildPig.get_poll(guild_id, kind)
    if poll is None:
        return {'status': Status.NOT_EXIST}
    await GuildPig.set_poll(guild_id, kind, None)
    window = Func.generate_current_timestamp() - config.guild_pig_feeder_window
    feeders = len(await GuildPig.get_feeders(guild_id, since=window))
    needed = max(config.guild_pig_poll_min_votes, round(feeders * config.guild_pig_poll_quorum))
    result = {'status': Status.SUCCESS, 'kind': kind, 'poll': poll, 'yes': yes, 'no': no,
              'needed': needed}
    if yes + no < needed:
        return {**result, 'status': Status.NOT_READY}
    if yes <= no:
        return {**result, 'status': Status.EXPIRED}
    if kind == 'shop':
        applied = await buy_server_item(guild_id, poll['item_id'], poll['price'], poll['currency'])
    elif kind == 'wear':
        applied = await wear_server_skin(guild_id, poll['item_id'], remove=poll.get('remove', False))
    else:
        return {**result, 'status': Status.NOT_EXIST}
    return {**result, 'status': applied['status']}


async def rename_guild_pig(guild_id: int, name: str):
    """Renames the community pig.

    Markdown characters are stripped rather than escaped, the same way a personal pig's are:
    the name is dropped into bold and italics all over the place, so a stray asterisk would
    unbalance whatever it lands in. A name that was nothing but those falls back to the
    default instead of leaving the pig nameless.
    """
    if not await GuildPig.is_setup(guild_id):
        return {'status': Status.NOT_EXIST}
    for symbol in config.illegal_name_symbols:
        name = name.replace(symbol, '')
    name = name.strip()[:config.guild_pig_name_max_length]
    if not name:
        return {'status': Status.NOT_EXIST, 'reason': 'empty'}
    await GuildPig.rename(guild_id, name)
    return {'status': Status.SUCCESS, 'name': name}


async def set_guild_pig_polls_allowed(guild_id: int, allowed: bool = None):
    """Turns members' voting on or off. Pass nothing to flip whatever it is now."""
    if not await GuildPig.is_setup(guild_id):
        return {'status': Status.NOT_EXIST}
    if allowed is None:
        allowed = not await GuildPig.get_polls_allowed(guild_id)
    await GuildPig.set_polls_allowed(guild_id, allowed)
    return {'status': Status.SUCCESS, 'allowed': allowed}


async def withdraw_server_money(user_id: int, guild_id: int, amount: int, currency: str = 'coins',
                                confirmed: bool = True):
    """Takes money out of the server's pig and puts it in one person's pocket.

    No tax, unlike donating - this is the server's own money coming back out, and taxing
    both ways would punish a server for parking money in the pig at all. Whether the person
    is allowed to do this at all is the front-end's business, since it is a discord
    permission and nothing this side can see.
    """
    amount = abs(amount)
    available = await Item.get_amount(currency, inventory=await GuildPig.get_inventory(guild_id))
    if amount > available:
        return {'status': Status.NO_MONEY, 'available': available}
    if not confirmed:
        return {'status': Status.PENDING, 'available': available}
    await User.transfer_item(from_guild=guild_id, to_user=user_id, item_id=currency, amount=amount,
                             reason='server_withdrawal')
    return {'status': Status.SUCCESS, 'amount': amount, 'available': available - amount}


async def propose_server_wear(user_id: int, guild_id: int, item_id: str, remove: bool = False,
                              bypass: bool = False):
    """Checks whether this person may put dressing the pig to the server right now.

    Same gate as a purchase, on the pig's own wardrobe instead of the shop. Like there, it
    opens nothing - the front-end posts the poll and hands it back through open_server_poll.
    """
    if not await GuildPig.is_setup(guild_id):
        return {'status': Status.NOT_EXIST}
    if await Item.get_type(item_id) != 'skin':
        return {'status': Status.NOT_EXIST}
    if await Item.get_amount(item_id, inventory=await GuildPig.get_inventory(guild_id)) < 1:
        return {'status': Status.NOT_ENOUGH_ITEMS}
    if await GuildPig.is_skin_worn(guild_id, item_id) != remove:
        # asked to put on what is already on, or take off what is not
        return {'status': Status.ALREADY_USED}
    if not remove:
        not_compatible = await GameFunc.get_not_compatible_active_skins(
            None, item_id, skins=await GuildPig.get_skin(guild_id, 'all'))
        if not_compatible:
            return {'status': Status.NOT_COMPATIBLE_SKINS, 'skins': not_compatible}
    if bypass:  # whoever runs the server does not need anyone's permission
        return {'status': Status.SUCCESS, 'bypass': True}
    if not await GuildPig.get_polls_allowed(guild_id):
        return {'status': Status.NOT_ALLOWED}
    if await GuildPig.get_poll(guild_id, 'wear') is not None:
        return {'status': Status.IN_PROCESS}
    window = Func.generate_current_timestamp() - config.guild_pig_feeder_window
    if str(user_id) not in await GuildPig.get_feeders(guild_id, since=window):
        return {'status': Status.NOT_A_CONTRIBUTOR}
    next_proposal = await GuildPig.get_last_proposal(guild_id, user_id) + config.guild_pig_proposal_cooldown
    if Func.generate_current_timestamp() < next_proposal:
        return {'status': Status.NOT_READY, 'try_again': next_proposal}
    return {'status': Status.SUCCESS, 'bypass': False}


async def wear_server_skin(guild_id: int, item_id: str, remove: bool = False):
    """Dresses or undresses the pig. Every layer of the skin at once - which of them to put
    on is not a thing a server can sensibly be asked in a yes/no vote."""
    if remove:
        await GuildPig.remove_skin(guild_id, item_id)
        return {'status': Status.SUCCESS}
    if await Item.get_amount(item_id, inventory=await GuildPig.get_inventory(guild_id)) < 1:
        return {'status': Status.NOT_ENOUGH_ITEMS}
    # the vote was cast on a pig that may since have been dressed differently, and it
    # already said yes to this skin - so whatever clashes comes off rather than refusing
    for skin in await GameFunc.get_not_compatible_active_skins(
            None, item_id, skins=await GuildPig.get_skin(guild_id, 'all')):
        await GuildPig.remove_skin(guild_id, skin)
    await GuildPig.set_skin(guild_id, item_id)
    return {'status': Status.SUCCESS}


async def buy_server_item(guild_id: int, item_id: str, price: int, currency: str):
    """Takes the money off the server and puts the item in its pig. The balance is checked
    here and nowhere earlier, because it is the balance at this moment that matters."""
    if await Item.get_amount(currency, inventory=await GuildPig.get_inventory(guild_id)) < price:
        return {'status': Status.NO_MONEY}
    await GuildPig.remove_item(guild_id, currency, price)
    await GuildPig.add_item(guild_id, await Item.clean_id(item_id), 1)
    return {'status': Status.SUCCESS}


async def preview_weekly_rewards(guild_id: int, since: int = None):
    """Works out who is owed what, without paying anyone.

    Split out from the payout so the numbers can be shown, tested and logged without moving
    items - and so the payout itself has nothing in it but the handing over.
    """
    # nothing is ever deleted from the feed list, so what somebody is owed for is whatever
    # they have fed since they were last paid - and that mark is their own. a window shared
    # by everybody would strand the feeds of anyone who fed too little to be paid, since the
    # window moves on without them and their feeds fall out of it forever.
    marks = await GuildPig.get_paid_until(guild_id)
    by_user = {}
    for feed in await GuildPig.get_feeds(guild_id):
        user_id = str(feed['user_id'])
        mark = since if since is not None else (marks.get(user_id) or 0)
        if feed['timestamp'] <= mark:
            continue
        entry = by_user.setdefault(user_id, {'kg': 0.0, 'feeds': 0, 'last': 0})
        entry['kg'] += feed['weight_added']
        entry['feeds'] += 1
        entry['last'] = max(entry['last'], feed['timestamp'])
    if not by_user:
        return {'status': Status.NOT_EXIST}

    # only people who fed enough are placed at all - the pile is shared out among them, so
    # letting somebody who will not be paid hold a podium slot would just push everyone else
    # down a place for nothing
    eligible = {u: e for u, e in by_user.items()
                if e['feeds'] >= config.guild_pig_reward_min_feeds}
    ranked = sorted(eligible.items(), key=lambda pair: pair[1]['kg'], reverse=True)

    # what the pig produced this time: what it gained, and a bit more if it is a big pig.
    # only weight it is being paid for counts - a feed below the minimum stays on the books
    # for next time, and counting it now as well would pay for it twice
    eligible_kg = sum(entry['kg'] for entry in eligible.values())
    weight_bonus = await GameFunc.get_guild_pig_weight_bonus(await GuildPig.get_weight(guild_id))
    jitter = config.guild_pig_poop_pool_jitter
    pool = round(eligible_kg * config.guild_pig_poop_per_kg * weight_bonus
                 * random.uniform(1 - jitter, 1 + jitter))

    # each share is what that person fed, counted for more if they placed
    shares = {}
    for place, (user_id, entry) in enumerate(ranked):
        rank_bonus = config.guild_pig_poop_rank_bonuses[place] \
            if place < len(config.guild_pig_poop_rank_bonuses) else 1
        shares[user_id] = entry['kg'] * rank_bonus
    total_share = sum(shares.values())

    # a share is hardly ever a whole number of poops. take everyone's whole part first, then
    # hand the few left over to whoever was cut shortest - that adds up to exactly the pile
    # without anybody's slice jumping, which rounding each share on its own does not
    exact = {user_id: pool * share / total_share if total_share else 0
             for user_id, share in shares.items()}
    amounts = {user_id: int(value) for user_id, value in exact.items()}
    leftover = pool - sum(amounts.values())
    for user_id in sorted(exact, key=lambda u: exact[u] - amounts[u], reverse=True)[:leftover]:
        amounts[user_id] += 1

    rewards = {}
    for place, (user_id, entry) in enumerate(ranked):
        rewards[user_id] = {'place': place, 'kg': round(entry['kg'], 1), 'feeds': entry['feeds'],
                            'rank_bonus': config.guild_pig_poop_rank_bonuses[place]
                            if place < len(config.guild_pig_poop_rank_bonuses) else 1,
                            'share': round(shares[user_id] / total_share, 4) if total_share else 0,
                            'amount': amounts[user_id], 'paid': amounts[user_id] > 0,
                            'counted_up_to': entry['last']}

    # anyone short of the minimum is still reported, so the caller can see they were skipped
    for user_id, entry in by_user.items():
        if user_id in rewards:
            continue
        rewards[user_id] = {'place': None, 'kg': round(entry['kg'], 1), 'feeds': entry['feeds'],
                            'rank_bonus': 1, 'share': 0, 'amount': 0, 'paid': False,
                            'counted_up_to': entry['last']}
    return {'status': Status.SUCCESS,
            'rewards': rewards,
            'pool': pool,
            'weight_bonus': round(weight_bonus, 2),
            'total_kg': round(sum(e['kg'] for e in by_user.values()), 1),
            'total_poop': sum(r['amount'] for r in rewards.values() if r['paid']),
            'item_id': config.guild_pig_poop_item}


async def pay_weekly_rewards(guild_id: int, since: int = None):
    """Hands out the week's pooping and marks how far each person has been paid.

    The feed list is never touched - the whole history stays. The payout timestamp is
    written before anything is given away: paying nobody because of a crash is recoverable
    by hand, paying everybody twice is not.
    """
    now = Func.generate_current_timestamp()
    preview = await preview_weekly_rewards(guild_id, since)
    if preview['status'] != Status.SUCCESS:
        await GuildPig.set_last_payout(guild_id, now)
        return preview
    await GuildPig.set_last_payout(guild_id, now)
    for user_id, reward in preview['rewards'].items():
        if not reward['paid']:
            continue
        await User.register_user_if_not_exists(int(user_id))
        await User.add_item(int(user_id), preview['item_id'], reward['amount'],
                               reason='server_payout')
    # the mark only moves for people who were actually paid. anyone short of the minimum
    # keeps theirs where it was, so what they fed still counts towards the next payout
    await GuildPig.set_paid_until(guild_id,
                                  {u: r['counted_up_to']
                                   for u, r in preview['rewards'].items() if r['paid']})
    return preview


async def pay_weekly_rewards_if_needed(guild_id: int):
    """Safe to call as often as you like - it decides on its own whether a week has turned.

    Returns the payout when one happened, and None otherwise.
    """
    last_payout = await GuildPig.get_last_payout(guild_id)
    if config.guild_pig_payout_period is not None:
        # a fixed gap since the last payout instead of the calendar, for testing
        if last_payout is not None and \
                Func.generate_current_timestamp() - last_payout < config.guild_pig_payout_period:
            return None
    elif last_payout is not None and last_payout >= Func.get_week_start():
        return None
    return await pay_weekly_rewards(guild_id)
