from ..db_api import *
from ..game_functions import GameFunc
from ..functions import Func

def duel(user_id: int, opponent_id: int, bet: int):
    if Item.get_amount('coins', user_id) < bet:
        return {'status': '400;no_money', 'user_id': user_id}
    if Item.get_amount('coins', opponent_id) < bet:
        return {'status': '400;no_money', 'user_id': opponent_id}
    chances = GameFunc.get_duel_winning_chances(user_id, opponent_id)
    winner_id = Func.random_choice_with_probability(chances)
    chances_copy = chances.copy()
    chances_copy.pop(winner_id)
    loser_id = list(chances_copy)[0]
    money_earned = int(round(bet * 1.9))
    User.remove_item(winner_id, 'coins', bet)
    User.remove_item(loser_id, 'coins', bet)
    User.add_item(winner_id, 'coins', money_earned)
    return {'status': 'success', 'winner': winner_id, 'loser': loser_id, 'money_earned': money_earned}