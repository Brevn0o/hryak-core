import json

from .connection import Connection
from ..functions import Func
from hryak import config


class Logs:
    """The economy ledger - every item created, destroyed or moved.

    `timestamp` and `log_type` are columns because every query filters on them;
    everything else about an event goes in `data`, so a new kind of log needs no
    migration.
    """

    @staticmethod
    async def add(log_type: str, **data):
        """Records one event. Never raises - a logging problem must not break the
        economy operation that was being logged."""
        try:
            await Connection.make_request(
                f"INSERT INTO {config.logs_schema} (timestamp, log_type, data) "
                f"VALUES (%s, %s, %s)",
                params=(Func.generate_current_timestamp(), log_type,
                        json.dumps({k: v for k, v in data.items() if v is not None},
                                   ensure_ascii=False, default=str)))
        except Exception as e:
            print(f'[logs] {log_type} not written: {e}')

    @staticmethod
    async def get(log_type: str = None, user_id=None, item_id: str = None,
                  since: int = None, until: int = None, limit: int = 100):
        """Events matching every filter given, newest first."""
        where, params = [], []
        if log_type is not None:
            where.append('log_type = %s')
            params.append(log_type)
        if user_id is not None:
            where.append("CAST(data->>'$.user_id' AS UNSIGNED) = %s")
            params.append(int(user_id))
        if item_id is not None:
            # both sides cast the same way: BINARY(64) is fixed width and pads with null
            # bytes, so an uncast literal would never match. Written this way it matches
            # and still uses the index.
            where.append("CAST(data->>'$.item_id' AS BINARY(64)) = CAST(%s AS BINARY(64))")
            params.append(item_id)
        if since is not None:
            where.append('timestamp >= %s')
            params.append(since)
        if until is not None:
            where.append('timestamp <= %s')
            params.append(until)
        rows = await Connection.make_request(
            f"SELECT id, timestamp, log_type, data FROM {config.logs_schema} "
            f"{'WHERE ' + ' AND '.join(where) if where else ''} "
            f"ORDER BY timestamp DESC, id DESC LIMIT %s",
            params=(*params, int(limit)), fetch=True, fetch_first=False)
        return [{'id': row[0], 'timestamp': row[1], 'log_type': row[2],
                 'data': json.loads(row[3]) if isinstance(row[3], str) else (row[3] or {})}
                for row in (rows or ())]

    @staticmethod
    async def count(log_type: str = None, since: int = None):
        where, params = [], []
        if log_type is not None:
            where.append('log_type = %s')
            params.append(log_type)
        if since is not None:
            where.append('timestamp >= %s')
            params.append(since)
        return await Connection.make_request(
            f"SELECT COUNT(*) FROM {config.logs_schema} "
            f"{'WHERE ' + ' AND '.join(where) if where else ''}",
            params=tuple(params) or None, fetch=True)

    @staticmethod
    async def delete_older_than(timestamp: int, batch_size: int = 10000):
        """Trims old events away, in chunks so the table is never locked for long.
        Returns how many rows went.

        Counts rather than reading ROW_COUNT(): every request here can land on a
        different pooled connection, and ROW_COUNT() only knows about its own.
        """
        async def remaining():
            return await Connection.make_request(
                f"SELECT COUNT(*) FROM {config.logs_schema} WHERE timestamp < %s",
                params=(timestamp,), fetch=True) or 0

        deleted, left = 0, await remaining()
        while left:
            await Connection.make_request(
                f"DELETE FROM {config.logs_schema} WHERE timestamp < %s LIMIT %s",
                params=(timestamp, batch_size))
            now_left = await remaining()
            if now_left == left:
                break  # nothing is going away; do not spin forever
            deleted += left - now_left
            left = now_left
        return deleted
