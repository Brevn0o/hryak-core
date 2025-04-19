from ..db_api import *
from ..game_functions import GameFunc
from ..functions import Func

async def duel(user_id: int, opponent_id: int, bet: int):
    await User.register_user_if_not_exists(user_id)
    await User.register_user_if_not_exists(opponent_id)
    if await Item.get_amount('coins', user_id) < bet:
        return {'status': '400;no_money', 'user_id': user_id}
    if await Item.get_amount('coins', opponent_id) < bet:
        return {'status': '400;no_money', 'user_id': opponent_id}
    chances = await GameFunc.get_duel_winning_chances(user_id, opponent_id)
    winner_id = Func.random_choice_with_probability(chances)
    chances_copy = chances.copy()
    chances_copy.pop(winner_id)
    loser_id = list(chances_copy)[0]
    money_earned = int(round(bet * 1.9))
    await User.remove_item(winner_id, 'coins', bet)
    await User.remove_item(loser_id, 'coins', bet)
    await User.add_item(winner_id, 'coins', money_earned)
    return {'status': 'success', 'winner_id': winner_id, 'loser': loser_id, 'money_earned': money_earned, 'chances': chances}