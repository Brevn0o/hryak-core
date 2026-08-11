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
            'discord_id varchar(32) UNIQUE',
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
    async def create_server_shop_table():
        columns = ['id int AUTO_INCREMENT PRIMARY KEY UNIQUE',
                   'timestamp varchar(32)',
                   'data json',
                   ]
        await Setup.create_table(columns, config.server_shop_schema)

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
    async def create_logs_table():
        """The economy ledger - one row per item generated, burned or transferred.

        Only the two things every query filters on get their own column; everything
        specific to the kind of event lives in `data`, so a new log type needs no
        migration. The indexes on user_id and item_id read them straight back out of
        the json, which is what keeps that cheap.
        """
        columns = ['id bigint unsigned AUTO_INCREMENT PRIMARY KEY',  # no UNIQUE - the primary
                                                                     # key already is one, and a
                                                                     # second copy of it costs
                                                                     # every insert for nothing
                   'timestamp bigint unsigned NOT NULL DEFAULT 0',
                   'log_type varchar(32) NOT NULL',
                   'data json',
                   ]
        await Setup.create_table(columns, config.logs_schema)
        indexes = [
            'idx_timestamp (timestamp)',
            'idx_type_timestamp (log_type, timestamp)',
            "idx_user_timestamp ((CAST(data->>'$.user_id' AS UNSIGNED)), timestamp)",
            # BINARY, not CHAR: a CHAR cast comes out as utf8mb4_0900_ai_ci while the
            # table is utf8mb4_general_ci, and that mismatch quietly makes the index
            # unusable. Item ids are exact lowercase slugs, so comparing bytes is right.
            "idx_item_timestamp ((CAST(data->>'$.item_id' AS BINARY(64))), timestamp)",
        ]
        for index in indexes:
            try:
                await Connection.make_request(f"ALTER TABLE {config.logs_schema} ADD INDEX {index}",
                                              commit=False)
            except Exception:
                pass  # already there - same as how the columns above are added

    @staticmethod
    async def create_guild_table():
        columns = ['id varchar(32) PRIMARY KEY UNIQUE',
                   'joined int',
                   'settings json',
                   'pig json',
                   ]
        await Setup.create_table(columns, config.guilds_schema)