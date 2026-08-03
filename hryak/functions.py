import datetime, random, json, os
import shutil

import aiocache
import aiofiles
import aiohttp
import requests
from scipy.interpolate import PchipInterpolator
import numpy as np

from . import config


def translate(locales, lang, format_options: dict = None):
    translated_text = 'translation_error'
    if type(locales) == dict:
        if lang not in locales or locales.get(lang) is None:
            lang = 'en'
        translated_text = locales[lang]
    elif type(locales) == str:
        translated_text = locales
    if type(translated_text) == list:
        translated_text = random.choice(translated_text)
    if format_options is not None:
        for k, v in format_options.items():
            translated_text = translated_text.replace('{' + k + '}', str(v))
    return translated_text

class Lava:

    @staticmethod
    def _raise_for_status(response):
        """raise_for_status() hides the body, which is where lava explains what it rejected."""
        if not response.ok:
            raise requests.HTTPError(
                f'{response.status_code} for {response.url}: {response.text[:500]}',
                response=response)

    @staticmethod
    async def create_order(user_id: str, reward_type: str, amount: float,
                     currency: str = "RUB", language: str = "EN") -> dict:
        """Creates a payment link.

        The offers are in "price on request" mode, so v3 takes the amount in the request
        itself - no need to rewrite the offer's price beforehand.
        """
        offer_id = config.lava_donate_options[reward_type]
        r = requests.post(
            "https://gate.lava.top/api/v3/invoice",
            headers={"X-Api-Key": config.lava_api_key, "Content-Type": "application/json"},
            json={
                "email": f"{user_id}@example.com",
                "offerId": offer_id,
                "currency": currency,
                "amount": amount,
                "buyerLanguage": language.upper(),
                "clientUtm": {"utm_content": user_id},
            },
            timeout=30,
        )
        Lava._raise_for_status(r)
        data = r.json()

        return {"invoice_id": data["id"], "url": data.get("paymentUrl")}

    @staticmethod
    async def get_status(invoice_id: str) -> str:
        resp = requests.get(
            f"https://gate.lava.top/api/v1/invoices/{invoice_id}",
            headers={"X-Api-Key": config.lava_api_key, "Content-Type": "application/json"},
            timeout=30
        )
        Lava._raise_for_status(resp)
        return str(resp.json().get("status", "unknown")).lower()


class Func:

    @staticmethod
    def generate_current_timestamp():
        return round(datetime.datetime.now().timestamp())

    @staticmethod
    def generate_random_pig_name(language):
        return f'{translate(config.pig_names[0], language)} {translate(config.pig_names[1], language)}'

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
    async def clear_db_cache(cache_id: str, func, *args):
        if cache_id not in aiocache.caches._config:
            return

        cache = aiocache.caches.get(cache_id)
        if not args:
            await cache.clear()
            return

        # callers pass the original args either as one tuple or positionally
        call_args = args[0] if len(args) == 1 and isinstance(args[0], tuple) else args
        await cache.delete(Func.cache_key_builder(func, *call_args))

    @staticmethod
    def cache_key_builder(func, *args, **kwargs):
        return f"{func.__module__}.{func.__name__}:{':'.join([str(i) for i in args])}:{':'.join([f'{k}={v}' for k, v in kwargs.items()])}"

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
    async def get_image_path_from_link(link: str, name: str = None):
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
                async with aiohttp.ClientSession() as session:
                    async with session.get(link) as response:
                        content = await response.read()
                async with aiofiles.open(path, 'wb') as f:
                    await f.write(content)
                return path
            except (aiohttp.ClientError, TimeoutError):
                continue
        return path

    @staticmethod
    def generate_temp_path(key_word: str, file_extension: str = None):
        for _ in range(100):
            path = f'{config.temp_folder_path}/{key_word}_{Func.generate_current_timestamp()}_{random.randrange(10000)}{f'.{file_extension}' if file_extension is not None else ''}'
            if not os.path.exists(path):
                return path

    @staticmethod
    async def add_log(log_type, **kwargs):
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
