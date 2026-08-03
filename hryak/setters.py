import sys

import aiocache
from aiocache import caches

from . import config


def _rebind_cached_functions():
    """Point already-decorated functions at the current cache config.

    aiocache resolves an alias to a cache instance when the decorator is applied - at
    import time - and keeps it on the decorator object. Reconfiguring afterwards would
    otherwise update the registry while every decorated function kept its old backend.
    """
    rebound = set()
    for module in list(sys.modules.values()):
        if not getattr(module, '__name__', '').startswith('hryak'):
            continue
        holders = [module] + [v for v in vars(module).values() if isinstance(v, type)]
        for holder in holders:
            for attribute in list(vars(holder).values()):
                function = getattr(attribute, '__func__', attribute)
                for cell in getattr(function, '__closure__', None) or ():
                    try:
                        decorator = cell.cell_contents
                    except ValueError:
                        continue
                    if isinstance(decorator, aiocache.cached) and decorator.alias:
                        decorator.cache = caches.get(decorator.alias)
                        # the decorator keeps its own reference and the wrapper exposes a
                        # copy as <function>.cache - keep them in step
                        function.cache = decorator.cache
                        rebound.add(id(decorator))
    return len(rebound)


def set_redis_cache(host: str, port: int = 6379, db: int = 0, password: str = None,
                    ssl: bool = False, ssl_verify: bool = True):
    """Share the data caches through redis so every front-end sees the same values.

    Use ssl=True for a rediss:// endpoint, and ssl_verify=False when the server presents
    a self-signed certificate. The 'default' alias stays in memory - it holds temp file
    paths and platform objects, which mean nothing outside the process that made them.
    """
    conf = config._memory_cache_config()
    for alias in config.shared_cache_aliases:
        entry = {
            'cache': 'aiocache.RedisCache',
            'endpoint': host,
            'port': port,
            'db': db,
            'password': password,
            'ssl': ssl,
            'ttl': config.cache_ttl,
            'serializer': {'class': 'aiocache.serializers.JsonSerializer'},
        }
        if ssl and not ssl_verify:
            entry['connection_pool_kwargs'] = {'ssl_cert_reqs': None}
        conf[alias] = entry
    caches.set_config(conf)
    return _rebind_cached_functions()


def set_lava_api_key(key: str):
    config.lava_api_key = key

def set_lava_donate_options(options: dict):
    config.lava_donate_options = options

def set_logs_path(path: str):
    config.logs_path = path

def set_test_mode(mode: bool):
    config.test = mode

def set_pig_feed_cooldown(cooldown: int):
    config.pig_feed_cooldown = cooldown

def set_pig_butcher_cooldown(cooldown: int):
    config.pig_butcher_cooldown = cooldown

def set_streak_timeout(timeout: int):
    config.streak_timeout = timeout

def set_github_version(version: bool):
    config.github_version = version

def set_bot_guilds(guilds: dict):
    config.bot_guilds = guilds

def set_temp_folder_path(path: str):
    config.temp_folder_path = path

def set_platform(platform: str):
    """Tells core which front-end it is running as, so user lookups use the right id column."""
    if platform not in config.supported_platforms:
        raise ValueError(f"unknown platform {platform!r}, expected one of {config.supported_platforms}")
    config.platform = platform