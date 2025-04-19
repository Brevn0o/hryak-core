import aiomysql

from .connection import Connection
from hryak import config


class Setup:

    @staticmethod
    async def create_table(columns, schema):
        try:
            await Connection.make_request(f"CREATE TABLE {schema} ({columns[0]})", commit=False)
        except Exception as e:
            pass
        try:
            await Connection.make_request(
                f"ALTER TABLE {schema} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;", commit=False)
        except Exception as e:
            pass
        for column in columns[1:]:
            try:
                await Connection.make_request(f"ALTER TABLE {schema} ADD COLUMN {column}", commit=False)
            except Exception as e:
                pass

    @staticmethod
    async def create_user_table():
        columns = [
            'id varchar(32) PRIMARY KEY UNIQUE',
            'created int DEFAULT 0',
            "pig json",
            "inventory json",
            "stats json",
            "events json",
            "history json",
            "rating json",
            "settings json",
            "orders json"
        ]
        await Setup.create_table(columns, config.users_schema)

    @staticmethod
    async def create_shop_table():
        columns = ['id int AUTO_INCREMENT PRIMARY KEY UNIQUE',
                   'timestamp varchar(32)',
                   'data json',
                   ]
        await Setup.create_table(columns, config.shop_schema)

    @staticmethod
    async def create_promo_code_table():
        columns = ['id varchar(128) PRIMARY KEY UNIQUE',
                   'created varchar(32)',
                   'users_used json',
                   'max_uses int',
                   'prise json',
                   'expires_in int'
                   ]
        await Setup.create_table(columns, config.promocodes_schema)

    @staticmethod
    async def create_guild_table():
        columns = ['id varchar(32) PRIMARY KEY UNIQUE',
                   'joined int',
                   'settings json',
                   ]
        await Setup.create_table(columns, config.guilds_schema)