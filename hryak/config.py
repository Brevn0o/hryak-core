import json

from cachetools import TTLCache

from hryak.setters import *

print(11111, pig_feed_cooldown)

users_schema = 'users'
promocodes_schema = 'promo_codes'
shop_schema = 'shop'
guilds_schema = 'guilds'

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

with open(f'pig_code/core/items_config.json', 'r', encoding='utf-8') as f:
    items = json.loads(f.read())

daily_shop_items_types = {
    'hat': 1,
    'glasses': 1,
    'body': 1,
    'pupils': 1,
    'other': 3
}
shops_emojis = {
    'daily_shop': '🎨',
    'case_shop': '📦',
    'consumables_shop': '💊',
    'tools_shop': '🔪',
    'premium_skins_shop': '💵',
    'coins_shop': '🪙',
    'donation_shop': '🍩',
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
        750: 0.25,
        1550: 0.49,
        3300: 0.99,
        7200: 1.99,
        20000: 4.99,
    }}

language_currencies = {
    'ru': 'RUB',
    'en': 'USD'
}

amount_of_hollars_per_unit_of_real_currency = {
    'RUB': 1,
    'USD': 50,
    'UAH': 2
}

currency_to_usd = {
    'RUB': 90,
    'USD': 1,
    'UAH': 40
}

currency_symbols = {
    'RUB': '₽',
    'USD': '$',
    'UAH': '₴ (UAH)'
}

payment_methods_for_languages = {
    'ru': ['aaio', 'donatepay', 'donatello'],
    'en': ['aaio']
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
image_links = {'inventory': 'https://thumbsnap.com/i/4EBKi23j.png',
               'invite': 'https://thumbsnap.com/i/JQ3RPzX1.png',
               'trade': 'https://thumbsnap.com/i/Hm1iX2Mj.png',
               'shop': 'https://thumbsnap.com/i/JkjRGKx2.png',
               'top': 'https://thumbsnap.com/i/2QLNAtCR.png',
               'coins_ru_ruble_prices': 'https://i.postimg.cc/yxCJCCcB/IMG-7540.png',
               'image_is_blocked': 'https://thumbsnap.com/i/EQ1EaKmW.png',
               'buffs': 'https://i.ibb.co/5Kq79Sp/26a1.webp',
               'quests': 'https://i.ibb.co/Htmxmxj/Quest-Main-Available-Icon-001.png'}
db_api_cash_size = 10
db_api_cash_ttl = 1

guild_settings = {'allow_say': False}
user_settings = {'language': 'en', 'blocked': False, 'block_reason': None, 'isolated': False, 'isolation_level': 0}
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

# embed colors
main_color = 0xc7604c
error_color = 0xc94312
warn_color = 0xe0bb36
success_color = 0x2fc256
premium_color = 0x61dfff

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
    'item.get_data': TTLCache(maxsize=1000, ttl=600000),
    'item.get_emoji': TTLCache(maxsize=1000, ttl=600000),
    'tech.__get_all_items': TTLCache(maxsize=1000, ttl=600000),
    'tech.get_all_items': TTLCache(maxsize=1000, ttl=600000)
}

pig_names = [
    {'en': ['Sleepy', 'Angry', 'Kind', 'Crazy', 'Drunk', 'High', 'Big', 'Stinky', 'Fat', 'Thin', 'Funny', 'Smart',
            'Dumb', 'Sexy', 'Chubby', 'Small', 'Large'],
     'ru': ['Грязный', 'Крутой', 'Сухой', 'Мокрый', 'Обкуренный', 'Мертвый', 'Вонючий', 'Сладкий', 'Непробиваемый',
            'Толстый', 'Тонкий', 'Смешной', 'Умный', 'Глупый', 'Сексуальный', 'Пухлый', 'Маленький', 'Большой']},
    {'en': ['Pig', 'Meat', 'Maxim', 'John', 'Jack', 'Chris', 'Anthony'],
     'ru': ['Хряк', 'Свин', 'Шашлык', 'Максим', 'Антон', 'Александр', 'Иван', 'Матвей', 'Даниил', 'Денис', 'Кирилл',
            'Дмитрий', 'Артем', 'Алексей', 'Егор', 'Станислав', 'Роман', 'Виктор', 'Илья', 'Никита', 'Владимир',
            'Михаил']},
]
