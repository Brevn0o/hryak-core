import json, random

from .connection import Connection
from ..functions import Func
from hryak import config


class Order:

    @staticmethod
    async def get_all_orders():
        orders = {}
        result = await Connection.make_request(
            f"SELECT orders FROM {config.users_schema} WHERE JSON_LENGTH(orders) > 0",
            commit=False,
            fetchall=True,
        )
        for i in result:
            for j in i:
                orders.update(json.loads(j))
        return orders

    @staticmethod
    async def get_user_orders(user_id):
        result = await Connection.make_request(
            f"SELECT orders FROM {config.users_schema} WHERE id = {user_id}",
            commit=False,
            fetch=True,
        )
        if result is not None:
            return json.loads(result)
        else:
            return {}

    @staticmethod
    async def set_new_orders(user_id, new_orders):
        new_orders = json.dumps(new_orders, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET orders = '{new_orders}' WHERE id = {user_id}"
        )

    @staticmethod
    async def create(user_id, order_id: str, items: dict, amount: float, currency: str, platform: str):
        orders = await Order.get_user_orders(user_id)
        orders[order_id] = {'status': 'in_process',
                            'items': items,
                            'platform': platform,
                            'amount': amount,
                            'currency': currency,
                            'timestamp': Func.generate_current_timestamp()}
        await Order.set_new_orders(user_id, orders)

    @staticmethod
    async def exists_in_db(order_id: str):
        if await Order.get_order(order_id) is None:
            return False
        return True

    @staticmethod
    async def get_order(order_id: str):
        orders = await Connection.make_request(
            f"SELECT JSON_EXTRACT(orders, CONCAT('$.', %s)) FROM {config.users_schema} WHERE JSON_CONTAINS_PATH(orders, 'one', '$.\"%s\"') = 1",
            params=(order_id, order_id),
            commit=False,
            fetch=True,
            fetchall=True)
        if orders and orders[0]:
            return json.loads(orders[0][0])

    @staticmethod
    async def get_status(order_id: str):
        order = await Order.get_order(order_id)
        return order['status']

    @staticmethod
    async def set_status(order_id: str, status: str):
        user_id = await Order.get_user(order_id)
        if user_id is None:
            return
        orders = await Order.get_user_orders(user_id)
        orders[order_id]['status'] = status
        await Order.set_new_orders(user_id, orders)

    @staticmethod
    async def get_items(order_id: str):
        order = await Order.get_order(order_id)
        return order['items']

    @staticmethod
    async def get_platform(order_id: str):
        order = await Order.get_order(order_id)
        return order['platform']

    @staticmethod
    async def get_amount(order_id: str):
        order = await Order.get_order(order_id)
        return order['amount']

    @staticmethod
    async def get_currency(order_id: str):
        order = await Order.get_order(order_id)
        return order['currency']

    @staticmethod
    async def get_user(order_id: str):
        users = await Connection.make_request(
            f"SELECT id FROM {config.users_schema} WHERE JSON_CONTAINS_PATH(orders, 'one', '$.\"%s\"') = 1",
            params=(order_id,),
            commit=False,
            fetch=True,
            fetchall=True)
        if users and users[0]:
            return json.loads(users[0][0])

    @staticmethod
    async def delete(order_id):
        user_id = await Order.get_user(order_id)
        if user_id is None:
            return
        orders = await Order.get_user_orders(user_id)
        orders.pop(order_id)
        await Order.set_new_orders(user_id, orders)

    @staticmethod
    async def generate_order_id(platform: str):
        order_id = 'error'
        if platform == 'donatello':
            while True:
                order_id = f'{random.randrange(1000, 10000)}'
                if not await Order.exists_in_db(order_id):
                    break
        return order_id