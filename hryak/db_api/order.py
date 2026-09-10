import json, random

from .connection import Connection
from .logs import Logs
from .schema import user_id_column
from ..functions import Func, Lava, Stripe
from hryak import config


class Order:

    @staticmethod
    async def get_all_orders():
        orders = {}
        result = await Connection.make_request(
            f"SELECT orders FROM {config.users_schema} WHERE JSON_LENGTH(orders) > 0",
            commit=False,
            fetchall=True,
            fetch=True
        )
        for i in result:
            for j in i:
                orders.update(json.loads(j))
        return orders

    @staticmethod
    async def get_user_orders(user_id):
        result = await Connection.make_request(
            f"SELECT orders FROM {config.users_schema} WHERE {user_id_column()} = %s",
            # as a string: discord_id is a varchar, and comparing it against an int makes
            # mysql coerce both to double, which past 15 digits stops being exact - two
            # accounts close together then read and write each other's orders
            params=(str(user_id),),
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
            f"UPDATE {config.users_schema} SET orders = %s WHERE {user_id_column()} = %s",
            params=(new_orders, str(user_id))
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
        # the row in users.orders is working state and is deleted the moment the order
        # settles, either way - so without a log line here a paid order leaves nothing
        # behind but the items it granted, and there is no way to ask what was sold, for
        # how much, or through which provider
        await Logs.add('order_created', user_id=user_id, order_id=order_id,
                       platform=platform, amount=amount, currency=currency, items=items)

    @staticmethod
    async def log_settled(order_id: str, outcome: str, status: str = None):
        """Records how an order ended, just before it is deleted.

        Read from the order rather than passed in, so the log cannot disagree with what
        was actually sold. Called while the row still exists - after the delete there is
        nothing left to read.
        """
        order = await Order.get_order(order_id)
        if order is None:
            return
        await Logs.add(f'order_{outcome}', user_id=await Order.get_user(order_id),
                       order_id=order_id, platform=order.get('platform'),
                       amount=order.get('amount'), currency=order.get('currency'),
                       items=order.get('items'), status=status or order.get('status'),
                       # how long the buyer took, which is the number that says whether a
                       # provider is worth keeping
                       seconds=Func.generate_current_timestamp() - int(order.get('timestamp') or 0))

    @staticmethod
    async def exists_in_db(order_id: str):
        if await Order.get_order(order_id) is None:
            return False
        return True

    @staticmethod
    async def get_order(order_id: str):
        orders = await Connection.make_request(
            # the path has to be built by mysql: a %s inside a quoted literal gets escaped
            # into '$."'id'"', and an unquoted $.id is invalid for numeric or dashed ids
            f"SELECT JSON_EXTRACT(orders, CONCAT('$.\"', %s, '\"')) FROM {config.users_schema} "
            f"WHERE JSON_CONTAINS_PATH(orders, 'one', CONCAT('$.\"', %s, '\"')) = 1",
            params=(order_id, order_id),
            commit=False,
            fetch=True,
            fetchall=True)
        if orders and orders[0]:
            return json.loads(orders[0][0])

    @staticmethod
    async def get_status(order_id: str, fetch: bool = False):
        order = await Order.get_order(order_id)
        if fetch:
            platform = order['platform']
            if platform == 'lava.top':
                return await Lava.get_status(order_id)
            if platform == 'stripe':
                return await Stripe.get_status(order_id)
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
    async def get_timestamp(order_id: str):
        order = await Order.get_order(order_id)
        return order['timestamp']

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
            f"SELECT {user_id_column()} FROM {config.users_schema} "
            f"WHERE JSON_CONTAINS_PATH(orders, 'one', CONCAT('$.\"', %s, '\"')) = 1",
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