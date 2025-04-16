from .config import (logs_path, test, pig_feed_cooldown,
                     pig_butcher_cooldown, streak_timeout)


def set_logs_path(path: str):
    global logs_path
    logs_path = path

def set_test_mode(mode: bool):
    global test
    test = mode

def set_pig_feed_cooldown(cooldown: int):
    global pig_feed_cooldown
    pig_feed_cooldown = cooldown

def set_pig_butcher_cooldown(cooldown: int):
    global pig_butcher_cooldown
    pig_butcher_cooldown = cooldown

def set_streak_timeout(timeout: int):
    global streak_timeout
    streak_timeout = timeout