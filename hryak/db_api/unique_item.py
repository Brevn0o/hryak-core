"""Items that exist exactly once, and what makes each of them itself.

The inventory can only say how many of something somebody has. That is all an ordinary
item needs, and it is why moving one is arithmetic. A mini-pig is not like that: it has
parents, a birthday, a rarity of its own, and two of them are not interchangeable.

So the inventory still holds nothing but {'amount': 1} under an id like
'minipig?i=a3f9c2', and everything that makes that one a particular mini-pig lives here,
in a row keyed by the 'i' alone. An item id is a composite - what kind of thing it is,
and which one - and only the second half is this table's business. Trading it is an
ordinary transfer, because there is no data to carry: the data never moved.

The row outlives the item on purpose. Somebody may butcher a mini-pig; its parents still
had it, and a family tree that forgets its dead ancestors is not a family tree.
"""
import json
import uuid

import aiocache

from .connection import Connection
from .item import Item
from ..functions import Func
from hryak import config


class UniqueItem:

    # ---- identity ----------------------------------------------------------

    @staticmethod
    async def extract_unique_id(item_id: str):
        """The 'i' out of an item id, or the value itself if that is what was passed.

        Callers hold whichever they happen to have - an inventory key is a full item id,
        while anything read back out of this table is already a handle - so every method
        here takes either and reduces it.
        """
        if not item_id:
            return None
        return (await Item.get_props(item_id)).get('i') or item_id

    @staticmethod
    async def generate_new_unique_id(attempts: int = 8) -> str:
        """A free id for a new one. This is what the table is keyed by.

        Eight hex characters is short enough to sit inside a Discord custom_id and wide
        enough that a clash is rare, but rare is not never - by the birthday bound they
        start showing up in the tens of thousands - so this asks before handing one out
        and rolls again if it is taken.

        The check is not the guarantee. Two of these running at once can still pick the
        same id between the look and the insert; what actually prevents a duplicate row
        is the INSERT IGNORE in create(). This is here so that a clash costs a reroll
        instead of a birth that fails for no visible reason.
        """
        for _ in range(attempts):
            unique_id = uuid.uuid4().hex[:8]
            if not await UniqueItem.exists(unique_id):
                return unique_id
        raise RuntimeError(
            f'could not generate a free unique id in {attempts} attempts - the id space '
            f'is too crowded for its length, widen the slice here')

    # ---- making and unmaking -----------------------------------------------

    @staticmethod
    async def create(item_id: str, data: dict, cur=None) -> bool:
        """Records one. False when that id is already taken, rather than overwriting it.

        Pass cur to run inside a caller's transaction - User.add_item does, so that the
        row and the inventory entry are written together or not at all.
        """
        sql = (f"INSERT IGNORE INTO {config.unique_items_schema} (id, created, data) "
               f"VALUES (%s, %s, CAST(%s AS JSON))")
        params = (await UniqueItem.extract_unique_id(item_id), Func.generate_current_timestamp(),
                  json.dumps(data or {}, ensure_ascii=False))
        if cur is not None:
            await cur.execute(sql, params)
            created = cur.rowcount > 0
        else:
            await Connection.make_request(sql, params=params, fetch=False)
            created = True
        # generate_new_unique_id asked exists() about this id a moment ago and exists()
        # is cached, so a "no such row" answer is sitting under it. Without dropping that,
        # the row just written reads back as absent until the ttl runs out
        await UniqueItem.clear_get_cache(item_id)
        return created

    @staticmethod
    async def remove(item_id: str):
        """Erases the record itself.

        Rarely what you want. Taking the item out of an inventory already stops anybody
        owning it, and the row left behind is the history - who its parents were, when it
        was born. Use this for something that should never have existed, not for
        something that stopped existing.
        """
        await Connection.make_request(
            f"DELETE FROM {config.unique_items_schema} WHERE id = %s",
            params=(await UniqueItem.extract_unique_id(item_id),))
        await UniqueItem.clear_get_cache(item_id)

    # ---- reading -----------------------------------------------------------

    @staticmethod
    @aiocache.cached(key_builder=Func.cache_key_builder, alias="unique_item.get")
    async def get(item_id: str):
        """The whole row as {'id', 'created', 'data'}, or None if there is no such item."""
        handle = await UniqueItem.extract_unique_id(item_id)
        # fetchall, because make_request without it hands back the first *column* of the
        # first row rather than the row - convenient for a single value, wrong for two
        rows = await Connection.make_request(
            f"SELECT created, data FROM {config.unique_items_schema} WHERE id = %s",
            params=(handle,), commit=False, fetch=True, fetchall=True)
        if not rows:
            return None
        created, data = rows[0]
        return {'id': handle, 'created': created,
                'data': json.loads(data) if data else {}}

    @staticmethod
    async def get_data(item_id: str) -> dict:
        """Just the data, {} when there is none. The common read."""
        row = await UniqueItem.get(item_id)
        return dict(row['data']) if row else {}

    @staticmethod
    async def get_created(item_id: str):
        """When it came into existence, in unix seconds. None if there is no such item."""
        row = await UniqueItem.get(item_id)
        return row['created'] if row else None

    @staticmethod
    async def exists(item_id: str) -> bool:
        return await UniqueItem.get(item_id) is not None

    @staticmethod
    async def get_many(item_ids) -> dict:
        """{handle: row} for several at once.

        A wardrobe page shows twenty of these. Asking for them one at a time is twenty
        round trips for one screen, which is how a list view quietly becomes the slowest
        thing in the bot.
        """
        handles = [h for h in [await UniqueItem.extract_unique_id(i) for i in item_ids] if h]
        if not handles:
            return {}
        placeholders = ', '.join(['%s'] * len(handles))
        rows = await Connection.make_request(
            f"SELECT id, created, data FROM {config.unique_items_schema} "
            f"WHERE id IN ({placeholders})",
            params=tuple(handles), commit=False, fetch=True, fetchall=True)
        return {r[0]: {'id': r[0], 'created': r[1],
                       'data': json.loads(r[2]) if r[2] else {}}
                for r in (rows or [])}

    # ---- writing -----------------------------------------------------------

    @staticmethod
    async def set_data(item_id: str, data: dict):
        """Replaces the whole data object."""
        await Connection.make_request(
            f"UPDATE {config.unique_items_schema} SET data = CAST(%s AS JSON) WHERE id = %s",
            params=(json.dumps(data, ensure_ascii=False), await UniqueItem.extract_unique_id(item_id)))
        await UniqueItem.clear_get_cache(item_id)

    @staticmethod
    async def update_data(item_id: str, **fields):
        """Merges fields into the data object without reading it back first.

        JSON_MERGE_PATCH rather than read-change-write for the usual reason: two things
        naming and rehoming the same mini-pig at once would otherwise overwrite each
        other with whichever snapshot was taken first.

        It cannot empty anything. Merging {} into an object leaves that object as it was,
        and merging None deletes the key outright - so use clear_field for that, not a
        value that looks empty.
        """
        await Connection.make_request(
            f"UPDATE {config.unique_items_schema} "
            f"SET data = JSON_MERGE_PATCH(COALESCE(data, JSON_OBJECT()), CAST(%s AS JSON)) "
            f"WHERE id = %s",
            params=(json.dumps(fields, ensure_ascii=False), await UniqueItem.extract_unique_id(item_id)))
        await UniqueItem.clear_get_cache(item_id)

    @staticmethod
    async def clear_field(item_id: str, field: str):
        """Empties one field to {}, which update_data cannot do.

        JSON_SET replaces the value outright where a merge patch would fold the empty
        object into whatever is already there and change nothing.
        """
        await Connection.make_request(
            f"UPDATE {config.unique_items_schema} "
            f"SET data = JSON_SET(COALESCE(data, JSON_OBJECT()), %s, JSON_OBJECT()) "
            f"WHERE id = %s",
            params=(f'$.{field}', await UniqueItem.extract_unique_id(item_id)))
        await UniqueItem.clear_get_cache(item_id)

    @staticmethod
    async def set_created(item_id: str, created: int):
        """Overrides the birthday. For importing something that existed before this table
        did - the column is stamped on create and there is no other reason to move it."""
        await Connection.make_request(
            f"UPDATE {config.unique_items_schema} SET created = %s WHERE id = %s",
            params=(int(created), await UniqueItem.extract_unique_id(item_id)))
        await UniqueItem.clear_get_cache(item_id)

    # ---- cache -------------------------------------------------------------

    @staticmethod
    async def clear_get_cache(item_id: str):
        """Both spellings, because get() is cached under whatever it was called with.

        Through Func, the same way every other getter does it - the key is built by
        cache_key_builder from the module and arguments, not from the alias, so writing
        one out by hand produces a key that never matches and a cache that never clears.
        """
        await Func.clear_db_cache('unique_item.get', UniqueItem.get, (item_id,))
        handle = await UniqueItem.extract_unique_id(item_id)
        if handle != item_id:
            await Func.clear_db_cache('unique_item.get', UniqueItem.get, (handle,))
