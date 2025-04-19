import aiomysql
from hryak import config

class ConnectionPool:
    def __init__(self):
        self.pool = None
        self.host = None
        self.port = None
        self.user = None
        self.password = None
        self.db = None

    def set_config(self, **db_config):
        self.host = db_config['host']
        self.port = db_config['port']
        self.user = db_config['user']
        self.password = db_config['password']
        self.db = db_config['database']

    async def create_pool(self):
        self.pool = await aiomysql.create_pool(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            db=self.db,
            autocommit=True,
            maxsize=50,
        )

    async def close(self):
        if self.pool is not None:
            self.pool.close()
            await self.pool.wait_closed()

    async def get_connection(self):
        if self.pool is None:
            raise RuntimeError("Connection pool not initialized.")
        if self.pool._loop.is_closed():
            raise RuntimeError("Event loop is closed.")
        return await self.pool.acquire()

    async def release_connection(self, conn):
        if self.pool is None or conn is None:
            return
        try:
            self.pool.release(conn)
        except Exception as e:
            print(f"[Release Error] {e}")


pool = ConnectionPool()


class Connection:

    @staticmethod
    async def make_request(query, params=None, commit=True, fetch=False, fetch_first=True, fetchall=False,
                           executemany=False):
        conn = None
        cur = None
        result = None
        try:
            conn = await pool.get_connection()
            cur = await conn.cursor()

            if executemany:
                await cur.executemany(query, params)
            else:
                await cur.execute(query, params)

            print(query, result)
            if fetch:
                result = await cur.fetchall() if fetchall or not fetch_first else await cur.fetchone()

            if fetch_first and not fetchall:
                result = result[0] if result else None

            if commit:
                await conn.commit()

            return result



        except Exception as e:
            print(e)
            if conn:
                await conn.rollback()
                await conn.ensure_closed()
            raise e

        finally:
            print(result)
            if cur:
                await cur.close()
            if conn:
                await pool.release_connection(conn)