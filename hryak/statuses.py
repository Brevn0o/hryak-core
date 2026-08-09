"""Status codes returned by hryak.requests.

The strings are what actually travels between core and a front-end. Import these
constants instead of writing the literals, so a typo fails at import time rather
than silently never matching.
"""


class Status:
    """The 'status' key returned by every request."""
    SUCCESS = 'success'
    IN_PROCESS = 'in_process'
    PENDING = 'pending'
    PENDING_CHOOSE_PARTS = 'pending;choose_parts'

    ALREADY_USED = '400;already_used'
    EXPIRED = '400;expired'
    NO_ITEM_KNIFE = '400;no_item;knife'
    NO_MONEY = '400;no_money'
    NO_TRADE_ID = '400;no_trade_id'
    NOT_COMPATIBLE_SKINS = '400;not_compatible_skins'
    NOT_ENOUGH_ITEMS = '400;not_enough_items'
    NOT_A_CONTRIBUTOR = '400;not_a_contributor'
    NOT_ALLOWED = '400;not_allowed'
    NOT_EXIST = '400;not_exist'
    NOT_READY = '400;not_ready'
    USED_TOO_MANY_TIMES = '400;used_too_many_times'


class TradeStatus:
    """The 'trade_status' key, also stored on the trade itself."""
    IN_PROCESS = 'in_process'
    TRANSFERRING = 'transferring'
    TAX_PROCESSING = 'tax_processing'
    TAX_PROCESSING_SUCCESS = 'tax_processing_success'
    SUCCESS = 'success'
