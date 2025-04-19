import json
import random

from .connection import Connection
from ..functions import Func
from ..functions import translate
from .. import config


# from .stats import Stats


class Events:

    @staticmethod
    async def get_events(user_id):
        result = await Connection.make_request(
            f"SELECT events FROM {config.users_schema} WHERE id = {user_id}",
            commit=False,
            fetch=True,
        )
        if result is not None:
            return json.loads(result)
        else:
            return {}

    @staticmethod
    async def update_events(user_id, new_events):
        new_events = json.dumps(new_events, ensure_ascii=False)
        await Connection.make_request(
            f"UPDATE {config.users_schema} SET events = %s WHERE id = {user_id}",
            (new_events,)
        )

    @staticmethod
    # @cached(TTLCache(maxsize=utils_config.db_api_cash_size, ttl=utils_config.db_api_cash_ttl))
    async def get_event(user_id, event_id):
        events = await Events.get_events(user_id)
        if event_id in events:
            return events[event_id]

    @staticmethod
    async def add(user_id, title,
            description,
            description_format: dict = None,
            event_id: str = None, expires_in: int = None):
        events = await Events.get_events(user_id)
        if type(title) == dict:
            title = title.copy()
        if type(description) == dict:
            description = description.copy()
            if description_format is not None:
                for lang in description:
                    description[lang] = translate(description, lang, description_format)
        elif type(description) == str and description_format is not None:
            description = description.format(**description_format)
        if event_id is None:
            event_id = str(random.randrange(10000, 999999))
        events[event_id] = {
            'title': title,
            'description': description,
            'expires_in': expires_in,
            'created': Func.generate_current_timestamp()
        }
        await Events.update_events(user_id, events)

    @staticmethod
    async def remove(user_id, event_id):
        events = await Events.get_events(user_id)
        events.pop(event_id)
        await Events.update_events(user_id, events)

