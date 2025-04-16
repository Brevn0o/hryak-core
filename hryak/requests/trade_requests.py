from ..db_api import Trade, Item, User, Pig
from ..game_functions import GameFunc


def trade(user1_id, user2_id, trade_id):
    if user1_id == user2_id:
        return {'status': '400;same_user'}
    if trade_id is None:
        return {'status': '400;no_trade_id'}
    agree_number = Trade.get_agree_number(trade_id)
    if agree_number == 2 and Trade.get_status(trade_id) == 'in_process':
        Trade.set_status(trade_id, 'tax_processing')
        return {'status': 'success', 'trade_status': 'tax_processing'}
    if Trade.get_status(trade_id) == 'tax_processing':
        if Trade.get_tax_splitting_vote(trade_id, user1_id) == 'tax_split_1':
            Trade.set_tax_splitting(trade_id, 'tax_split_1')
            for item_id, amount in GameFunc.get_trade_total_tax(trade_id).items():
                Trade.add_tax_to_pay(trade_id, user1_id, item_id, amount)
        elif Trade.get_tax_splitting_vote(trade_id, user2_id) == 'tax_split_2':
            Trade.set_tax_splitting(trade_id, 'tax_split_2')
            for item_id, amount in GameFunc.get_trade_total_tax(trade_id).items():
                Trade.add_tax_to_pay(trade_id, user2_id, item_id, amount)
        elif Trade.get_total_tax_splitting_votes(trade_id, 'tax_split_equal') == 2:
            Trade.set_tax_splitting(trade_id, 'tax_split_equal')
            for item_id, amount in GameFunc.get_trade_total_tax(trade_id).items():
                Trade.add_tax_to_pay(trade_id, user1_id, item_id, amount // 2)
                amount //= 2
                Trade.add_tax_to_pay(trade_id, user2_id, item_id, amount)
        if Trade.get_tax_splitting(trade_id) is not None or not GameFunc.get_trade_total_tax(trade_id):
            Trade.set_status(trade_id, 'tax_processing_success')
            return {'status': 'success', 'trade_status': 'tax_processing_success'}
    if Trade.get_status(trade_id) == 'tax_processing_success':
        if Trade.get_status(trade_id) == 'transferring':
            return
        Trade.set_status(trade_id, 'transferring')
        for user_id in [user2_id, user2_id]:
            total_items = Trade.get_items(trade_id, user_id)
            tax_to_pay = Trade.get_tax_to_pay(trade_id, user_id)
            for key, value in tax_to_pay.items():
                if key in total_items:
                    total_items[key]["amount"] += value["amount"]
                else:
                    total_items[key] = value
            for item_id, data in total_items.items():
                if Item.get_amount(item_id, user_id) < data['amount']:
                    return {'status': '400;not_enough_items', 'user_id': user_id, 'item_id': item_id}
        for user_id in [user1_id, user2_id]:
            for item_id, data in Trade.get_items(trade_id, user_id).items():
                user_id_to_give = user1_id if user_id == user2_id else user1_id
                user_id_to_remove = user1_id if user_id != user2_id else user2_id
                amount = data['amount']
                User.transfer_item(user_id_to_remove, user_id_to_give, item_id, amount)
                if Item.get_amount(item_id, user_id_to_remove) <= 0 and Item.get_type(item_id) == 'skin':
                    Pig.remove_skin(user_id, item_id)
            for item_id, data in Trade.get_tax_to_pay(trade_id, user_id).items():
                amount_to_remove = data['amount']
                User.remove_item(user_id, item_id, amount_to_remove)
                if Item.get_amount(item_id, user_id) <= 0 and Item.get_type(item_id) == 'skin':
                    Pig.remove_skin(user_id, item_id)
        Trade.set_status(trade_id, 'success')
        return {'status': 'success', 'trade_status': 'success'}
