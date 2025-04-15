from mysql.connector import pooling

class MySQLPool:
    __instance = None

    @staticmethod
    def get_instance():
        if MySQLPool.__instance is None:
            raise Exception("Pool not initialized. Call create_pool() first.")
        return MySQLPool.__instance

    def __init__(self):
        self.pools = []

    def create_pool(self, host, port, user, password, database):
        MySQLPool.__instance = self
        self.pools.append(pooling.MySQLConnectionPool(
            pool_name="mypool",
            pool_size=32,
            host=host,
            port=port,
            user=user,
            password=password,
            database=database,
            charset='utf8'
        ))

    def get_connection(self):
        for pool in self.pools:
            try:
                return pool.get_connection()
            except:
                continue
        # if all failed, try recreating pool
        raise Exception("All connection pools failed.")


# singleton instance
pool = MySQLPool()