import json
import os

from cachetools import TTLCache
from aiocache import cached, caches

logs_path = None
test = False
github_version = False
supported_platforms = ('discord',)
platform = None  # set by the front-end via setters.set_platform
pig_feed_cooldown = 4 * 3600
pig_butcher_cooldown = 40 * 3600
streak_timeout = 24.5 * 3600
doctor_price = 5
bot_guilds = []
temp_folder_path = None

lava_api_key = None
lava_donate_options = dict()

users_schema = 'users'
promocodes_schema = 'promo_codes'
shop_schema = 'shop'
guilds_schema = 'guilds'

trade_data = {}

default_pig = {'name': 'Hryak',
               'weight': 1,
               'feed_history': [],
               'butcher_history': [],
               'buffs': {},
               'genetic': {
                   'tail': 'default_body',
                   'left_ear': 'default_body',
                   'left_eye': 'white_eyes',
                   'right_eye': 'white_eyes',
                   'left_pupil': 'black_pupils',
                   'right_pupil': 'black_pupils',
                   'right_ear': 'default_body',
                   'nose': 'default_body',
                   'body': 'default_body',
                   'eyes': 'white_eyes',
                   'pupils': 'black_pupils',
               },
               'skins': {'body': None,
                         'tattoo': None,
                         'tail': None,
                         'left_ear': None,
                         'makeup': None,
                         'mouth': None,
                         'left_eye': None,
                         'right_eye': None,
                         'left_pupil': None,
                         'right_pupil': None,
                         'middle_ear': None,
                         'right_ear': None,
                         'suit': None,
                         'glasses': None,
                         'nose': None,
                         'piercing_nose': None,
                         'face': None,
                         'piercing_ear': None,
                         'back': None,
                         'hat': None,
                         'legs': None,
                         'tie': None}}
default_pig_body_genetic = ['default_body']
default_pig_pupils_genetic = ['black_pupils', 'blue_pupils', 'green_pupils',
                              'orange_pupils', 'pink_pupils', 'yellow_pupils', 'purple_pupils']
default_pig_eyes_genetic = ['white_eyes']
default_stats = {'pig_fed': 0, 'money_earned': 0, 'commands_used': {}, 'items_used': {}, 'items_sold': {}, 'streak': 0,
                 'successful_orders': 0, 'dollars_donated': 0,
                 'language_changed': False}
default_history = {'feed_history': [], 'butcher_history': [], 'shop_history': [], 'streak_history': []}

default_item = {
    'id': 'none',
    'name': {},
    'description': {},
    'type': None,
    'skin_config': {},
    'emoji': '🔴',
    'inventory_type': None,
    'rarity': None,
    'cooked_item_id': None,
    'market_price': None,
    'market_price_currency': None,
    'shop_category': None,
    'shop_cooldown': None,
    'buffs': None,
    'salable': None,
    'sell_price': None,
    'sell_price_currency': None,
    'tradable': None,
    'case_drops': None,
    'requirements': None,
    'image': None
}

skin_layers_rules = {
    'mouth': {'before': [
        'nose',
    ]},
    'glasses': {'before': [
        'nose',
    ]},
    'nose': {'before': [
    ],
        'after': [
            'left_eye',
            'right_eye',
            'left_pupil',
            'right_pupil',
        ]},
    'piercing_nose': {'after': [
        'nose'
    ]},
    'piercing_ear': {'after': [
        'right_ear',
    ]},
    'hat': {
        'after': ['suit'],
        'hide': ['middle_ear']
    }}


package_path = os.path.dirname(__file__)

with open(os.path.join(package_path, 'items_config.json'), 'r', encoding='utf-8') as f:
    items = json.loads(f.read())


def _absolutize_asset_paths(node):
    # image paths in items_config.json are stored relative to this package (bin/images/...),
    # so they resolve regardless of the working directory the bot is launched from
    if isinstance(node, dict):
        return {k: _absolutize_asset_paths(v) for k, v in node.items()}
    if isinstance(node, list):
        return [_absolutize_asset_paths(v) for v in node]
    if isinstance(node, str) and node.startswith('bin/'):
        return os.path.join(package_path, node)
    return node


items = _absolutize_asset_paths(items)

daily_shop_items_types = {
    'hat': 1,
    'glasses': 1,
    'body': 1,
    'pupils': 1,
    'other': 3
}

base_buff_multipliers = {
    'weight': 1,
    'pooping': 1,
    'vomit_chance': .15,
}

coins_prices = {750: 25,
                1550: 49,
                3300: 99,
                7200: 199,
                20000: 499} # coins: hollars

donate_coins_prices = {  # coins: real_currency
    'ru': {  # RUB
        750: 25.00,
        1550: 49.00,
        3300: 99.00,
        7200: 199.00,
        20000: 499.00,
    },
    'en': {  # USD
        750: 0.49,
        1550: 0.99,
        3300: 1.99,
        7200: 3.99,
        20000: 8.99,
    },
    'uk': {
        750: 12.50,
        1550: 24.50,
        3300: 49.50,
        7200: 99.50,
        20000: 249.50,
    }}

language_currencies = {
    'ru': 'RUB',
    'en': 'USD',
    'uk': 'UAH'
}

amount_of_hollars_per_unit_of_real_currency = {
    'RUB': 1,
    'USD': 50,
    'UAH': 2
}

currency_to_usd = {
    'RUB': 100,
    'USD': 1,
    'UAH': 40
}

currency_symbols = {
    'RUB': '₽',
    'USD': '$',
    'UAH': '₴ (UAH)'
}

payment_methods_for_languages = {
    'uk': ['donatello'],
    'ru': ['lava.top', 'donatello'],
    'en': ['lava.top', 'donatello']
}

fight_gifs = ['https://thumbsnap.com/i/3A83K3Ub.gif', 'https://thumbsnap.com/i/bKNDTHvr.gif',
              'https://media.tenor.com/mTxSXMy_kZAAAAAM/pig-dog.gif',
              'https://i.makeagif.com/media/10-11-2019/YgT9Fl.gif', 'https://tenor.com/view/dipshinn-pig-gif-20510409']
win_gifs = ['https://thumbsnap.com/i/wMCKTND2.gif',
            'https://thumbsnap.com/i/23B2Eyuo.gif',
            'https://thumbsnap.com/i/23B2Eyuo.gif',
            'https://thumbsnap.com/i/GggXBtEp.gif',
            'https://thumbsnap.com/i/DTt4Myh4.gif',
            'https://thumbsnap.com/i/g61XmvJJ.gif',
            'https://thumbsnap.com/i/i5EZi4mk.gif',
            'https://thumbsnap.com/i/hKJoXUqJ.gif',
            'https://thumbsnap.com/i/WptnXC5A.gif']
image_links = {'image_is_blocked': 'https://thumbsnap.com/i/EQ1EaKmW.png'}
db_api_cash_size = 10
db_api_cash_ttl = 1

guild_settings = {'allow_say': False}
user_settings = {'language': 'en', 'blocked': False, 'block_reason': None, 'top_participate': True}
emotions_erase_cords = {'sad': [(668, 904, 855, 849, 734, 740),
                                (917, 842, 1150, 917, 1085, 734)],
                        'happy': [(695, 970, 865, 970, 865, 1030, 695, 1030),
                                  (1115, 985, 900, 985, 900, 1030, 1110, 1030)],
                        'angry': [(604, 498, 394, 658, 762, 832), (758, 842, 1220, 670, 840, 546)],
                        'sus': [(760, 786, 1268, 786, 1018, 426)],
                        'dont_care': [(328, 774, 732, 782, 654, 444),
                                      (760, 786, 1268, 786, 1018, 426)]}

ignore_users_in_top = [715575898388037676]

trade_data = {}


pig_ages = {
    0: '1',
    20: '2',
    50: '3',
    100: '4',
    300: '5',
    500: '6',
    1000: '7',
}

rarity_colors = {
    '1': 0x858784,
    '2': 0x45ff4b,
    '3': 0x4d9aff,
    '4': 0xc14dff,
    '5': 0xff3d33,
    '6': 0xffee54,
    'custom': 0xa8ffd5,
    'star': 0x17fffb,
    'exclusive': 0xffeb8a,
}

db_caches = {
    'user.get_inventory': TTLCache(maxsize=1000, ttl=600000),
    'user.get_settings': TTLCache(maxsize=1000, ttl=600000),
    'user.get_rating': TTLCache(maxsize=1000, ttl=600000),
    'item.get_data': TTLCache(maxsize=1000, ttl=600000),
    'item.get_emoji': TTLCache(maxsize=1000, ttl=600000),
    'pig.get': TTLCache(maxsize=1000, ttl=600000),
    'shop.get_data': TTLCache(maxsize=1000, ttl=600000),
    'history.get': TTLCache(maxsize=1000, ttl=600000),
    'tech.__get_all_items': TTLCache(maxsize=1000, ttl=600000),
    'tech.get_all_items': TTLCache(maxsize=1000, ttl=600000)
}
cache_ttl = 600000
# mutable state - every front-end has to agree on these, so they can go in a shared cache
shared_cache_aliases = (
    'user.get_inventory', 'user.get_settings', 'user.get_rating',
    'pig.get', 'shop.get_data', 'history.get',
)
local_cache_aliases = (
    'item.get_data', 'item.get_emoji', 'tech.__get_all_items', 'tech.get_all_items',
)


def _memory_cache_config():
    conf = {'default': {'cache': 'aiocache.SimpleMemoryCache', 'ttl': cache_ttl}}
    for alias in local_cache_aliases + shared_cache_aliases:
        conf[alias] = {'cache': 'aiocache.SimpleMemoryCache', 'ttl': cache_ttl}
    return conf


caches.set_config(_memory_cache_config())

pig_names = [
    {'en': ['Sleepy', 'Angry', 'Kind', 'Crazy', 'Drunk', 'High', 'Big', 'Stinky', 'Fat', 'Skinny', 'Funny', 'Smart',
            'Dumb', 'Sexy', 'Silly', 'Small', 'Big', 'Wet'],
     'ru': ['Грязный', 'Крутой', 'Сухой', 'Мокрый', 'Обкуренный', 'Мертвый', 'Вонючий', 'Сладкий', 'Непробиваемый',
            'Толстый', 'Тонкий', 'Смешной', 'Умный', 'Глупый', 'Сексуальный', 'Пухлый', 'Маленький', 'Большой'],
     'uk': ['Брудний', 'Крутий', 'Сухий', 'Мокрий', 'Обкурений', 'Мертвий', 'Смердючий', 'Солодкий', 'Непробивний',
            'Товстий', 'Тонкий', 'Смішний', 'Розумний', 'Дурний', 'Сексуальний', 'Пухкий', 'Маленький', 'Великий']},
    {'en': ['Pig', 'Meat', 'Maxim', 'John', 'Jack', 'Chris', 'Anthony', 'Joaquin', 'Danny'],
     'ru': ['Хряк', 'Свин', 'Шашлык', 'Максим', 'Антон', 'Александр', 'Иван', 'Матвей', 'Даниил', 'Денис', 'Кирилл',
            'Дмитрий', 'Артем', 'Алексей', 'Егор', 'Станислав', 'Роман', 'Виктор', 'Илья', 'Никита', 'Владимир',
            'Михаил'],
     'uk': ['Хряк', 'Свин', 'Шашлик', 'Максим', 'Антон', 'Олександр', 'Іван', 'Матвій', 'Данило', 'Денис', 'Кирило',
            'Дмитро', 'Артем', 'Олексій', 'Єгор', 'Станіслав', 'Роман', 'Віктор', 'Ілля', 'Микита', 'Володимир',
            'Михайло']},
]
