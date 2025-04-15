from .pool import pool

class Connection:

    @staticmethod
    def connect():
        return pool.get_instance().get_connection()

    @staticmethod
    def make_request(query, params: tuple = None, commit: bool = True, executemany: bool = False,
                     fetch: bool = False, fetch_first: bool = True, fetchall=False):
        connection = Connection.connect()
        fetch = True if fetchall else fetch
        try:
            with connection.cursor() as cursor:
                if not executemany:
                    cursor.execute(query, params)
                else:
                    cursor.executemany(query, params)
                if commit:
                    connection.commit()
                if fetch:
                    if fetchall:
                        return cursor.fetchall()
                    result = cursor.fetchone()
                    if fetch_first:
                        return result[0]
                    else:
                        return result
        finally:
            connection.close()