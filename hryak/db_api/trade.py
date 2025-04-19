import copy

from .user import User
from .. import config


class Trade:

    @staticmethod
    async def exists(trade_id):
        return trade_id in config.trade_data

    @staticmethod
    async def update_data(trade_id, new_trade):
        config.trade_data[trade_id] = new_trade

    @staticmethod
    async def get_data(trade_id):
        return config.trade_data[trade_id]

    @staticmethod
    async def create(trade_id, user1_id, user2_id, message):
        data = {'users': {str(user1_id): {'items': {}, 'agree': False, 'tax_splitting_vote': None, 'tax_to_pay': {}},
                          str(user2_id): {'items': {}, 'agree': False, 'tax_splitting_vote': None, 'tax_to_pay': {}}},
                'status': 'in_process',
                'tax_splitting': None,
                'message': message}
        config.trade_data[trade_id] = data

    @staticmethod
    async def add_item(trade_id, user_id, item_id, amount: int):
        data = await Trade.get_data(trade_id)
        if item_id in data['users'][str(user_id)]['items']:
            data['users'][str(user_id)]['items'][item_id]['amount'] += amount
        else:
            data['users'][str(user_id)]['items'][item_id] = {'amount': amount}
        await Trade.update_data(trade_id, data)

    @staticmethod
    async def add_tax_to_pay(trade_id, user_id, item_id, amount: int):
        data = await Trade.get_data(trade_id)
        if item_id in data['users'][str(user_id)]['tax_to_pay']:
            data['users'][str(user_id)]['tax_to_pay'][item_id]['amount'] += amount
        else:
            data['users'][str(user_id)]['tax_to_pay'][item_id] = {'amount': amount}
        await Trade.update_data(trade_id, data)

    @staticmethod
    async def get_tax_to_pay(trade_id, user_id):
        data = await Trade.get_data(str(trade_id))
        return copy.deepcopy(data['users'][str(user_id)]['tax_to_pay'])

    @staticmethod
    async def clear_items(trade_id, user_id):
        data = await Trade.get_data(trade_id)
        data['users'][str(user_id)]['items'] = {}
        await Trade.update_data(trade_id, data)

    @staticmethod
    async def get_item_amount(trade_id, user_id, item_id):
        data = await Trade.get_data(trade_id)
        if item_id not in data['users'][str(user_id)]['items']:
            return 0
        else:
            return data['users'][str(user_id)]['items'][item_id]['amount']

    @staticmethod
    async def remove_item(trade_id, user_id, item_id, amount: int = None):
        data = await Trade.get_data(str(trade_id))
        if item_id not in data['users'][str(user_id)]:
            return
        else:
            if amount is not None:
                data['users'][str(user_id)][item_id]['items']['amount'] -= amount
            else:
                data['users'][str(user_id)].pop(item_id)
        await Trade.update_data(trade_id, data)

    @staticmethod
    async def get_users(trade_id):
        data = await Trade.get_data(trade_id)
        return copy.deepcopy(data['users'])

    @staticmethod
    async def get_user(client, trade_id, index: int = 0, fetch: bool = True):
        data = await Trade.get_data(str(trade_id))
        user_id = list(data['users'])[index]
        if not fetch:
            return user_id
        return await User.get_user(client, user_id)

    @staticmethod
    async def get_user_data(trade_id, user_id):
        data = await Trade.get_data(str(trade_id))
        return copy.deepcopy(data['users'][str(user_id)])

    @staticmethod
    async def get_items(trade_id, user_id):
        data = await Trade.get_data(str(trade_id))
        return copy.deepcopy(data['users'][str(user_id)]['items'])

    @staticmethod
    async def set_agree(trade_id, user_id, agree: bool = True):
        data = await Trade.get_data(str(trade_id))
        data['users'][str(user_id)]['agree'] = agree
        await Trade.update_data(trade_id, data)

    @staticmethod
    async def is_agree(trade_id, user_id):
        data = await Trade.get_data(str(trade_id))
        return data['users'][str(user_id)]['agree']

    @staticmethod
    async def set_tax_splitting_vote(trade_id, user_id, splitting_type: str):
        data = await Trade.get_data(str(trade_id))
        data['users'][str(user_id)]['tax_splitting_vote'] = splitting_type
        await Trade.update_data(trade_id, data)

    @staticmethod
    async def get_tax_splitting_vote(trade_id, user_id):
        data = await Trade.get_data(str(trade_id))
        return data['users'][str(user_id)]['tax_splitting_vote']

    @staticmethod
    async def get_total_tax_splitting_votes(trade_id, splitting_type):
        res = 0
        for user_id in await Trade.get_users(trade_id):
            if await Trade.get_tax_splitting_vote(trade_id, user_id) == splitting_type:
                res += 1
        return res

    @staticmethod
    async def set_status(trade_id, status: str):
        data = await Trade.get_data(str(trade_id))
        data['status'] = status
        await Trade.update_data(trade_id, data)

    @staticmethod
    async def get_status(trade_id):
        data = await Trade.get_data(str(trade_id))
        return data['status']

    @staticmethod
    async def set_tax_splitting(trade_id, tax_splitting: str):
        data = await Trade.get_data(str(trade_id))
        data['tax_splitting'] = tax_splitting
        await Trade.update_data(trade_id, data)

    @staticmethod
    async def get_tax_splitting(trade_id):
        data = await Trade.get_data(str(trade_id))
        return data['tax_splitting']

    @staticmethod
    async def set_message(trade_id, message):
        data = await Trade.get_data(str(trade_id))
        data['message'] = message
        await Trade.update_data(trade_id, data)

    @staticmethod
    async def get_message(trade_id):
        data = await Trade.get_data(str(trade_id))
        return data['message']

    @staticmethod
    async def get_agree_number(trade_id):
        res = 0
        for i in await Trade.get_users(trade_id):
            if await Trade.is_agree(trade_id, i):
                res += 1
        return res
