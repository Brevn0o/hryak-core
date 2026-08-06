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
server_shop_schema = 'server_shop'
guilds_schema = 'guilds'

trade_data = {}

default_pig = {'name': 'Hryak',
               'weight': 1,
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
default_guild_pig = {'name': 'Hryak',
                     'weight': 1,
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
                               'tie': None},
                     # same shape as a user's inventory: {item_id: {'amount': N}}
                     'inventory': {},
                     # [{'user_id': 123, 'timestamp': 123456, 'weight_added': 5}, ...]
                     'feeds': [],
                     'channel_id': None,  # where the pig lives
                     'message_id': None,  # the pig's message, kept up to date in place
                     'channel_created_by_bot': False,  # ours to delete when the pig moves out
                     'poll_channel_id': None,  # where votes are put to the server
                     'poll_channel_created_by_bot': False,
                     'notification_channel_id': None,  # where hryak announces what happened
                     'notification_channel_created_by_bot': False,
                     'admin_channel_id': None,  # the panel, hidden from everyone but staff
                     'admin_channel_created_by_bot': False,
                     'admin_message_id': None,  # the panel's message, redrawn in place
                     'category_id': None,  # holds whatever channels hryak made itself
                     'category_created_by_bot': False,
                     # one open vote per kind: {'shop': {...} or None, 'wear': {...} or None}
                     'polls': {},
                     # {user_id: timestamp} of the last poll each person started
                     'proposals': {},
                     'last_payout': None,  # when the pig last pooped, so a restart cannot double-pay
                     # {user_id: timestamp} - feeds after a person's mark are what they are
                     # still owed for. nothing is ever deleted from 'feeds'; this is what
                     # says which part of it has been settled, and for whom
                     'paid_until': {}}
# the community pig has its pupils drawn straight onto its face, so the eye whites a
# personal pig wears underneath them have nothing to sit in - anything listed here is left
# out whenever a pig is drawn with the community art
guild_pig_hidden_slots = ('eyes', 'left_eye', 'right_eye')
# stripped from any pig name - it gets dropped into bold and italics all over the place,
# so a stray one would unbalance whatever markdown it lands in
illegal_name_symbols = ('*', '`', '_', '~', '|', '#', '\\')
guild_pig_name_max_length = 32
guild_pig_feed_cooldown = 12 * 3600
guild_pig_poll_durations = {'shop': 24 * 3600, 'wear': 12 * 3600}  # TESTING: shop was 24 * 3600
guild_pig_proposal_cooldown = 48 * 3600  # per person, whatever they are proposing
guild_pig_feeder_window = 7 * 24 * 3600  # who counts as an active member of the server
guild_pig_poll_quorum = .25
guild_pig_poll_min_votes = 3

guild_pig_poop_item = 'community_poop'
guild_pig_payout_period = None  # TESTING: normally None
guild_pig_poop_per_kg = 1
guild_pig_poop_pool_jitter = .15  # +/-15%, so a payout is never quite the same twice
guild_pig_reward_min_feeds = 2  # drive-by feeding does not get paid
guild_pig_reward_top_shown = 10
guild_pig_poop_rank_bonuses = (2, 1.5, 1.25)  # 1st, 2nd, 3rd
guild_pig_poop_weight_bonus = ([0, 1000, 10000, 100000, 1000000],  # pig weight, kg
                               [1, 1.1, 1.3, 1.7, 2.2])           # multiplier

default_pig_body_genetic = ['default_body']
default_pig_pupils_genetic = ['black_pupils', 'blue_pupils', 'green_pupils',
                              'orange_pupils', 'pink_pupils', 'yellow_pupils', 'purple_pupils']
default_pig_eyes_genetic = ['white_eyes']
default_stats = {'pig_fed': 0, 'money_earned': 0, 'commands_used': {}, 'items_used': {}, 'items_sold': {}, 'streak': 0,
                 'successful_orders': 0, 'dollars_donated': 0,
                 'language_changed': False}
default_history = {'feed_history': [], 'butcher_history': [], 'shop_history': [], 'streak_history': [],
                   'server_feed_history': []}

default_item = {
    'id': 'none',
    'name': {},
    'description': {},
    'type': None,
    'emoji': '🔴',
    'inventory_type': None,
    'rarity': None,
    'cooked_item_id': None,
    # anything that differs between a personal pig and a server one lives in a context
    'individual_config': {
        'skin_config': {},
        'market_price': None,
        'market_price_currency': None,
        'shop_category': None,
        'shop_cooldown': None,
        'buffs': None,
        'buff_duration': None,
        'salable': None,
        'sell_price': None,
        'sell_price_currency': None,
        'tradable': None,
        'case_drops': None,
        'requirements': None,
        'image': None,
        'tax': None,
        'cases': {},
        'wealth_impact': None,
    },
    'server_config': {},
}
item_default_context = 'individual'
# what a server borrows from the individual config when it has none of its own: how the
# item looks, never what it costs - a missing server price means it is not sold to servers
item_context_fallback_keys = ('skin_config', 'image')


def item_in_context(item: dict, context: str = None) -> dict:
    """Flattens an item for one context, so callers see the fields at the top level the
    way they were before individual_config and server_config existed."""
    if context is None:
        context = item_default_context
    flat = {k: v for k, v in item.items() if not k.endswith('_config') or k == 'skin_config'}
    default = item.get(f'{item_default_context}_config') or {}
    if context == item_default_context:
        flat.update(default)
    else:
        flat.update({k: v for k, v in default.items() if k in item_context_fallback_keys})
        flat.update(item.get(f'{context}_config') or {})
    return flat


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

# What the servers' weekly shop puts out, the same way daily_shop_items_types works: how
# many of each skin type to draw, with 'other' covering everything not named above it. Ask
# for more than exist of a type and it simply offers all of them. Keep the total well under
# the catalogue or the rotation stops meaning anything.
weekly_shop_items_types = {
    'hat': 2,
    'glasses': 1,
    'pupils': 2,
    'other': 1
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

guild_settings = {'allow_say': False, 'language': 'en'}
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
    'pig.get', 'guild_pig.get', 'guild.get_settings', 'shop.get_data', 'history.get',
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
