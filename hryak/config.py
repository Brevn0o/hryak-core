import datetime
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
logs_schema = 'logs'

# The one-off "hryak is back" message to people who played before the bot went quiet.
# Only somebody who actually played is worth writing to - anybody below this many feeds
# tried it once and stopped, and messaging them is noise for them and risk for us.
comeback_min_feeds = 5
comeback_dormant_days = 60
# Ordering. Whoever was still playing when the bot went quiet is written to first: they
# did not choose to leave, it disappeared on them, so they are the likeliest to want it
# back. Last feeds are grouped into weeks rather than compared exactly - two people who
# both stopped that final week are equally "there at the end", and between them the one
# who had played more is the better prospect.
comeback_recency_band_days = 7
comeback_feed_band = 50
# Deliberately not coins: active players hold a median of ~38, so a currency gift to
# thousands of returners would swamp the economy. Consumables cost it nothing.
comeback_gift = {'rare_case': 2, 'cookie': 1}
comeback_send_delay = 5.0  # seconds between DMs, to stay well inside the rate limit

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
                     # whether ordinary members may put buying and wearing to a vote. off
                     # leaves those to whoever runs the server, who never needed a vote anyway
                     'polls_allowed': True,
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
                 'language_changed': False,
                 # whether a reminder of each kind is currently outstanding: set when the dm
                 # goes out, cleared by the thing it was reminding about. keeps one reminder
                 # per cooldown rather than one per time the task happens to run
                 'notifications_sent': {'feed_reminder': False, 'butcher_reminder': False,
                                        'server_feed_reminder': False}}
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


# Seasonal stock. An item may carry a shop_availability in its context config saying
# when it is allowed to be sold:
#
#     "shop_availability": {"from": "09-01", "to": "11-01"}
#
# A bound written MM-DD comes round every year, which is what a holiday wants - the
# halloween case should return next october without anybody editing a date. A bound
# written YYYY-MM-DD happens once and never again.
item_availability_key = 'shop_availability'

# Which money comes first when one shop page mixes them. A price only means anything
# against another price in the same currency - five cookies is not cheaper than a hundred
# and twenty coins, it is a different question - so a page groups by this and sorts within
# the group. Anything not named here sorts after everything that is.
shop_currency_order = ('coins', 'hollars', 'cookie')


def _availability_date(bound: str, year: int):
    """One end of a window as a date, and whether it named its own year.

    A bound without a year is anchored to the year it is being compared against, which is
    what makes MM-DD repeat.
    """
    parts = [int(p) for p in bound.split('-')]
    if len(parts) == 3:
        return datetime.date(*parts), True
    return datetime.date(year, *parts), False


def item_available_now(item: dict, context: str = None, now: datetime.datetime = None) -> bool:
    """Whether an item may be sold at this moment.

    An item with no window is always for sale, so everything that existed before seasons
    did carries on untouched.

    'from' is inclusive from midnight and 'to' is exclusive, so a window ending 11-01 is
    over the instant november begins rather than lasting through the day. A window whose
    start falls after its end wraps the new year - {"from": "12-15", "to": "01-05"} is a
    christmas window, not an empty one.

    Read in UTC, like the weekly rotation, so a season turns over at the same moment
    everywhere instead of wherever the bot happens to be running.
    """
    window = (item_in_context(item, context) or {}).get(item_availability_key)
    if not window:
        return True
    start, end = window.get('from'), window.get('to')
    if not start or not end:
        return True
    today = (now or datetime.datetime.now(datetime.timezone.utc)).date()
    try:
        start_date, start_dated = _availability_date(start, today.year)
        end_date, end_dated = _availability_date(end, today.year)
    except (TypeError, ValueError):
        # a malformed window should not quietly hide an item from the shop forever
        print(f'[availability] {item.get("id")} has an unreadable window: {window}')
        return True
    if start_dated or end_dated:
        return start_date <= today < end_date
    # neither named a year, so this repeats - and may run through new year's eve
    if start_date <= end_date:
        return start_date <= today < end_date
    return today >= start_date or today < end_date


def validate_items(items_to_check: dict = None, root: str = None) -> list:
    """Every way an item can be quietly wrong, checked in one place.

    None of these raise anywhere - they simply make the item behave oddly, and always
    somewhere far from the config that caused it. A skin tagged as an ordinary inventory
    item never reaches the wardrobe, so its owner can never wear it. An empty shop_cooldown
    used to take the buy button down with an IndexError. A skin config that exists in one
    context and not the other took a whole embed with it. Each of those cost real time to
    find from the symptom, and each is one line to spot from here.

    Returns a list of (item_id, problem) - reporting rather than raising, since a bad
    entry should be shouted about on boot, not stop the bot from starting.
    """
    import os
    items_to_check = items if items_to_check is None else items_to_check
    root = os.path.dirname(os.path.abspath(__file__)) if root is None else root
    found = []

    def contexts(item):
        return (('individual', item.get('individual_config') or {}),
                ('server', item.get('server_config') or {}))

    for item_id, item in items_to_check.items():
        if item.get('type') == 'skin':
            # the wardrobe list is filtered on this, and it is the only way to wear one
            if item.get('inventory_type') != 'wardrobe':
                found.append((item_id, f"is a skin but inventory_type is "
                                       f"{item.get('inventory_type')!r}, so it never reaches the wardrobe"))
            if not any((cfg.get('skin_config') or {}).get('type') for _, cfg in contexts(item)):
                found.append((item_id, 'is a skin with no skin_config.type in either context'))

        for name, cfg in contexts(item):
            if isinstance(cfg.get('shop_cooldown'), dict) and not cfg['shop_cooldown']:
                found.append((item_id, f'[{name}] shop_cooldown is an empty dict - '
                                       f'use null for "no limit"'))
            if cfg.get('shop_category') and cfg.get('market_price') is None:
                found.append((item_id, f"[{name}] is listed in the "
                                       f"{cfg['shop_category']!r} shop with no price"))
            # a price only has to name its money when something can actually be paid
            if cfg.get('market_price') is not None and not cfg.get('market_price_currency') \
                    and (cfg.get('shop_category') or cfg.get('salable')):
                found.append((item_id, f'[{name}] has a price but no currency'))
            if cfg.get('salable') and cfg.get('sell_price') is None:
                found.append((item_id, f'[{name}] is salable but has no sell_price'))

            window = cfg.get(item_availability_key)
            if window and not item_available_now({'individual_config': {item_availability_key: window}}):
                pass  # a closed season is normal; only an unreadable one is worth saying

            paths = [cfg['image']] if isinstance(cfg.get('image'), str) else []
            for layer in ((cfg.get('skin_config') or {}).get('layers') or {}).values():
                paths += [(layer or {}).get(k) for k in ('image', 'shadow')
                          if isinstance((layer or {}).get(k), str)]
            for path in paths:
                if path.startswith('http'):
                    continue
                if not os.path.exists(os.path.join(root, path)):
                    found.append((item_id, f'[{name}] points at a missing file: {path}'))
    return found


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

# The servers' shop has a page per price bracket - an item goes to whichever one its
# server_config shop_category names. Each page draws its own mix the way daily_shop_items_types
# does: how many of each skin type, with 'other' covering everything not named above it.
# Ask for more of a type than exists and it simply offers all of them. Keep each total well
# under that page's catalogue or the rotation stops meaning anything.
server_shop_tiers = {
    'weekly_entry': {'pupils': 2, 'hat': 2, 'other': 1},
    'weekly_mid': {'hat': 1, 'other': 2},
    # 'other' with nothing named above it means "any of them", so no item in the bracket
    # is unreachable. two of three a week, so something a server is saving for is usually
    # on the shelf when it finally has the money
    'weekly_high': {'other': 2},
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
    'ru': ['donatello'],
    'en': ['donatello']
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

guild_settings = {'allow_say': False, 'language': 'en',
                  'join_channel': None, 'join_message': None}
user_settings = {'language': 'en', 'blocked': False, 'block_reason': None, 'top_participate': True,
                 'notifications': {'feed_reminder': True, 'butcher_reminder': True,
                                   # off by default, unlike the other two. Feeding a community pig is
                                   # something most people never do, and the reminder loop checks
                                   # readiness per opted-in user in python - switching this on for
                                   # everybody would mean walking the whole userbase every minute
                                   'server_feed_reminder': False}}
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
