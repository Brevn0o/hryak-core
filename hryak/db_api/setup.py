import mysql.connector

from .connection import Connection
from hryak import config


class Setup:

    @staticmethod
    def create_table(columns, schema):
        try:
            Connection.make_request(f"CREATE TABLE {schema} ({columns[0]})", commit=False)
        except mysql.connector.errors.ProgrammingError:
            pass
        try:
            Connection.make_request(
                f"ALTER TABLE {schema} CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_general_ci;", commit=False)
        except mysql.connector.errors.ProgrammingError:
            pass
        for column in columns[1:]:
            try:
                Connection.make_request(f"ALTER TABLE {schema} ADD COLUMN {column}", commit=False)
            except Exception as e:
                pass

    @staticmethod
    def create_user_table():
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
        Tech.create_table(columns, config.users_schema)

    @staticmethod
    def create_shop_table():
        columns = ['id int AUTO_INCREMENT PRIMARY KEY UNIQUE',
                   'timestamp varchar(32)',
                   'data json',
                   ]
        Tech.create_table(columns, config.shop_schema)

    @staticmethod
    def create_promo_code_table():
        columns = ['id varchar(128) PRIMARY KEY UNIQUE',
                   'created varchar(32)',
                   'users_used json',
                   'max_uses int',
                   'prise json',
                   'expires_in int'
                   ]
        Tech.create_table(columns, config.promocodes_schema)

    @staticmethod
    def create_guild_table():
        columns = ['id varchar(32) PRIMARY KEY UNIQUE',
                   'joined int',
                   'settings json',
                   ]
        Tech.create_table(columns, config.guilds_schema)