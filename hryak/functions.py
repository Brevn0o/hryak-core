import datetime, random, json, os
import shutil

import aiocache
import aiofiles
import requests
from scipy.interpolate import PchipInterpolator
import numpy as np

from . import config


def translate(locales, lang, format_options: dict = None):
    translated_text = 'translation_error'
    if type(locales) == dict:
        if lang not in locales:
            lang = 'en'
        if lang not in locales:
            lang = list(locales)[0]
        translated_text = locales[lang]
    elif type(locales) == str:
        translated_text = locales
    if type(translated_text) == list:
        translated_text = random.choice(translated_text)
    if format_options is not None:
        for k, v in format_options.items():
            translated_text = translated_text.replace('{' + k + '}', str(v))
    return translated_text


class Func:

    @staticmethod
    def generate_current_timestamp():
        return round(datetime.datetime.now().timestamp())

    @staticmethod
    def common_elements(list_of_lists):
        common_set = set(list_of_lists[0])
        for lst in list_of_lists[1:]:
            common_set = common_set.intersection(lst)
        return list(common_set)

    @staticmethod
    def random_choice_with_probability(dictionary):
        """Selects a random key from a dictionary based on weighted probabilities.

        Example:
            probabilities = {
                "item1": 50,  # 50% chance
                "item2": 30,  # 30% chance
                "item3": 20   # 20% chance
            }
            result = Func.random_choice_with_probability(probabilities)
            print(result)  # Output will be "item1", "item2", or "item3"
        """
        total_probability = sum(dictionary.values())
        random_number = random.uniform(0, total_probability)
        cumulative_probability = 0

        for key, probability in dictionary.items():
            cumulative_probability += probability
            if random_number <= cumulative_probability:
                return key

    @staticmethod
    def calculate_probabilities(dictionary, round_to: int = 2):
        total = sum(dictionary.values())
        probabilities = {}

        for key, value in dictionary.items():
            probability = (value / total) * 100
            probabilities[key] = round(probability, round_to)

        return probabilities

    @staticmethod
    def clear_db_cache(cache_id, params: tuple = None):
        if cache_id not in config.db_caches:
            return
        if params is None:
            config.db_caches[cache_id].clear()
            return
        try:
            config.db_caches[cache_id].pop(params)
        except KeyError:
            pass

    @staticmethod
    async def get_image_temp_path_from_path_or_link(p: str):
        if p.startswith('http'):
            return await Func.get_image_path_from_link(p)
        else:
            return await Func.get_image_temp_path_from_path(p)

    @staticmethod
    @aiocache.cached(ttl=86400)
    async def get_image_temp_path_from_path(init_path: str):
        dest_path = Func.generate_temp_path(f'{random.randrange(1, 10000)}{os.path.basename(init_path)}')
        shutil.copy2(init_path, dest_path)
        return dest_path

    @staticmethod
    @aiocache.cached(ttl=86400)
    async def get_image_path_from_link(link: str, folder_path: str = None, name: str = None):
        if name is None:
            name = random.randrange(10000, 99999)
        if not link.startswith('http'):
            return link
        file_extension = 'png'
        if len(link.split('.')) > 1:
            if link.split('.')[-1] in ['png', 'webp', 'gif', 'jpg']:
                file_extension = link.split('.')[-1]
        path = Func.generate_temp_path(name, file_extension=file_extension)
        for i in range(3):
            try:
                if file_extension in ['gif']:
                    async with aiofiles.open(path, 'wb') as file:
                        for chunk in requests.get(link, stream=True).iter_content(1024):
                            await file.write(chunk)
                else:
                    async with aiofiles.open(path, 'wb') as f:
                        await f.write(requests.get(link).content)
            except requests.exceptions.ConnectionError:
                continue
        return path

    @staticmethod
    def generate_temp_path(key_word: str, file_extension: str = None):
        for _ in range(100):
            path = f'{config.temp_folder_path}/{key_word}_{Func.generate_current_timestamp()}_{random.randrange(10000)}{f'.{file_extension}' if file_extension is not None else ''}'
            if not os.path.exists(path):
                return path

    @staticmethod
    def add_log(log_type, **kwargs):
        current_time = datetime.datetime.now().isoformat()
        log_entry = {
            'timestamp': current_time,
            'type': log_type,
        }
        log_entry.update({k: v for k, v in kwargs.items() if isinstance(v, (str, int, float, bool, list, dict, set))})
        log_file_path = config.logs_path
        if os.path.exists(log_file_path) and os.path.getsize(log_file_path) > 0:
            with open(log_file_path, "rb+") as log_file:
                log_file.seek(-1, os.SEEK_END)
                last_char = log_file.read(1)
                if last_char == b']':
                    log_file.seek(-1, os.SEEK_END)
                    log_file.truncate()
                    log_file.write(b',\n')
            with open(log_file_path, "a", encoding="utf-8") as log_file:
                log_file.write(json.dumps(log_entry, indent=4, ensure_ascii=False))
                log_file.write("\n]")
        else:
            with open(log_file_path, "w", encoding="utf-8") as log_file:
                log_file.write("[\n")
                log_file.write(json.dumps(log_entry, indent=4, ensure_ascii=False))
                log_file.write("\n]")
