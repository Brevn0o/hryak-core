"""Names of things in the database, and how they are keyed."""
from hryak import config


def user_id_column():
    """The column user lookups filter on, decided by the front-end at startup.

    Every platform stores its own id on the same row, so a person who has linked
    both accounts is found by whichever column the running front-end uses.
    """
    if config.platform is None:
        raise RuntimeError('platform is not set - call hryak.setters.set_platform() before using the db')
    elif config.platform == 'discord':
        return 'discord_id'
    return None
