from . import config


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

def set_bot_guilds(guilds: list):
    config.bot_guilds = guilds