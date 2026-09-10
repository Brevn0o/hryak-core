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


class Stripe:
    """Stripe checkout, over the rest api directly.

    No sdk on purpose. The official one is synchronous, and a blocking http call inside
    the event loop stalls every command in every server until it returns - which is what
    the requests-based Lava calls above already do, and is the one thing not worth
    copying. aiohttp is already a dependency.

    Stripe takes form encoding rather than json, with brackets for nesting. Only a handful
    of keys are needed here, so they are written out flat rather than built by a generic
    flattener nobody else would use.
    """

    API = 'https://api.stripe.com/v1'
    # currencies stripe bills in units of 1, where the amount is not multiplied by 100.
    # None of the three the shop offers is one, but a wrong guess here charges a hundred
    # times too much, so it is written down rather than assumed
    ZERO_DECIMAL = {'BIF', 'CLP', 'DJF', 'GNF', 'JPY', 'KMF', 'KRW', 'MGA', 'PYG',
                    'RWF', 'UGX', 'VND', 'VUV', 'XAF', 'XOF', 'XPF'}
    # checkout only accepts languages it has a translation for, and rejects the whole
    # request for one it does not know. Ukrainian is not among them, so passing the bot's
    # own language straight through would fail every uk purchase - 'auto' lets stripe pick
    # from the browser instead, which is a better answer than an error
    LOCALES = {'en', 'ru'}

    @staticmethod
    def to_minor_units(amount: float, currency: str) -> int:
        """Money as stripe wants it: an integer of the smallest unit, so 4.99 -> 499.

        Rounded, never truncated - int(4.99 * 100) is 498 in binary floating point, and
        undercharging by a cent on every purchase is the sort of thing nobody notices for
        a year.
        """
        if currency.upper() in Stripe.ZERO_DECIMAL:
            return int(round(amount))
        return int(round(amount * 100))

    @staticmethod
    async def _request(method: str, path: str, data: dict = None) -> dict:
        """One call to stripe, with its error body kept.

        Stripe explains what it rejected in the response body, the same way lava does, and
        raise_for_status would throw that away.
        """
        headers = {'Authorization': f'Bearer {config.stripe_api_key}'}
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(method, f'{Stripe.API}{path}',
                                       headers=headers, data=data) as response:
                body = await response.text()
                if response.status >= 400:
                    raise RuntimeError(
                        f'stripe {response.status} for {method} {path}: {body[:500]}')
                return json.loads(body)

    @staticmethod
    async def create_order(user_id: str, reward_type: str, amount: float,
                           currency: str = 'USD', language: str = 'EN') -> dict:
        """Opens a checkout session and hands back its id and the page to send them to.

        The price is built per session rather than pointing at a product created on
        stripe's side: the buyer types how many hollars they want, so there is no fixed
        price to point at. Lava solves the same problem with its "price on request" mode.

        The discord id rides in client_reference_id, which is what a paid session is
        matched back to an order by - the same job lava's clientUtm.utm_content does.
        """
        product_name = config.stripe_donate_options.get(reward_type, reward_type)
        data = {
            'mode': 'payment',
            'client_reference_id': str(user_id),
            'line_items[0][quantity]': 1,
            'line_items[0][price_data][currency]': currency.lower(),
            'line_items[0][price_data][unit_amount]': Stripe.to_minor_units(amount, currency),
            'line_items[0][price_data][product_data][name]': product_name,
            'locale': language.lower() if language.lower() in Stripe.LOCALES else 'auto',
            'success_url': config.stripe_success_url,
            'cancel_url': config.stripe_cancel_url,
        }
        session = await Stripe._request('POST', '/checkout/sessions', data=data)
        return {'invoice_id': session['id'], 'url': session.get('url')}

    @staticmethod
    async def get_status(session_id: str) -> str:
        """Where a checkout session got to, in the words the order loop already knows.

        payment_status is the one that matters - a session can read 'complete' while the
        money is still not taken. 'paid' is the only answer that means the money arrived.

        A session stripe has expired is reported as failed so the order is cleared out
        rather than polled for the two further days the order timeout allows.
        """
        session = await Stripe._request('GET', f'/checkout/sessions/{session_id}')
        if str(session.get('payment_status', '')).lower() == 'paid':
            return 'success'
        if str(session.get('status', '')).lower() == 'expired':
            return 'failed'
        return 'in_process'


class Func:

    @staticmethod
    def generate_current_timestamp():
        return round(datetime.datetime.now().timestamp())

    @staticmethod
    def get_week_start(timestamp: int = None):
        """Timestamp of the most recent Sunday 00:00 UTC.

        Pinned to UTC rather than the machine's idea of midnight, so the weekly rotation
        and the weekly payout land at the same moment for every server no matter where
        the bot happens to be running.
        """
        moment = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc) \
            if timestamp is not None else datetime.datetime.now(datetime.timezone.utc)
        midnight = moment.replace(hour=0, minute=0, second=0, microsecond=0)
        # isoweekday(): monday is 1, sunday is 7 - so sunday is 0 days back
        return round((midnight - datetime.timedelta(days=moment.isoweekday() % 7)).timestamp())

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

