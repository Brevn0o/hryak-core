import asyncio
import concurrent

import aiocache
import numpy as np
from cachetools import TTLCache, cached
from scipy.interpolate import PchipInterpolator
from PIL import Image, ImageDraw

from .db_api import *
from .functions import Func
from . import config


class Hidden:

    @staticmethod
    def get_user_tax_percent(user_id, currency: str, wealth: dict):
        if currency == 'coins':
            pchip_function = PchipInterpolator(np.array([0, 1000, 10000, 100000, 1000000000]),
                                               np.array([0, 5, 10, 15, 30]))
        elif currency == 'hollars':
            pchip_function = PchipInterpolator(np.array([0, 100, 1000, 10000, 1000000]),
                                               np.array([0, 5, 10, 15, 30]))
        else:
            pchip_function = PchipInterpolator(np.array([0, 1000000]),
                                               np.array([5, 5]))
        wealth = wealth[currency] if currency in wealth else 0
        tax = pchip_function(wealth)
        return round(float(tax), 1)

    @staticmethod
    async def get_duel_winning_chances(user1_id: int, user2_id: int):
        chances = {}
        for user_id in [user1_id, user2_id]:
            chances[user_id] = 100
            chances[user_id] += await Pig.get_weight(user_id) / 2
            if await Pig.get_time_to_next_feed(user_id) != -1:
                chances[user_id] += 20
        chances = Func.calculate_probabilities(chances, 1)
        return chances

    @staticmethod
    @cached(TTLCache(maxsize=1000, ttl=86400))
    def remove_transparency(image_path):
        with Image.open(image_path) as img:
            bbox = img.getbbox()
            img = img.crop(bbox)
            img.save(image_path)
        return image_path

    @staticmethod
    @aiocache.cached(ttl=86400)
    async def build_pig(skins: tuple, genetic: tuple = None, eye_emotion: str = None, remove_transparency: bool = True):
        try:
            skins = dict(skins)
            if genetic is None:
                genetic = config.default_pig['genetic']
            else:
                genetic = dict(genetic)
            hide_skins = []
            hide_skins_raw = {}
            for item_id in skins.values():
                if await Item.exists(item_id) and await Item.get_skins_to_hide(item_id) is not None:
                    hide_skins_raw[await Item.get_skin_type(item_id)] = await Item.get_skins_to_hide(item_id)
            for i in config.skin_layers_rules:
                if skins[i] is not None:
                    if 'hide' in config.skin_layers_rules[i]:
                        if i in hide_skins_raw:
                            hide_skins_raw[i] += config.skin_layers_rules[i]['hide']
                        else:
                            hide_skins_raw[i] = config.skin_layers_rules[i]['hide']
            for k, v in hide_skins_raw.copy().items():
                for i in v:
                    if i not in config.default_pig['skins'] and not await Item.exists(i):
                        continue
                    skin_type = i
                    if i in await Tech.get_all_items():
                        skin_type = await Item.get_skin_type(i)
                    if skin_type in hide_skins_raw and list(config.default_pig['skins']).index(skin_type) < list(
                            config.default_pig['skins']).index(k):
                        hide_skins_raw.pop(skin_type)
            for v in hide_skins_raw.values():
                hide_skins += v
            ordered_layers = []
            for skin_type in config.default_pig['skins']:
                skin = skins[skin_type]
                if skin is None and skin_type in genetic:
                    skin = genetic[skin_type]
                if skin is None or skin_type not in config.default_pig['skins']:
                    continue
                if skin_type in ['body', 'tail', 'left_ear', 'right_ear', 'nose', 'left_eye', 'right_eye', 'left_pupil',
                                 'right_pupil', 'middle_ear']:

                    for element in await Item.get_skin_layer(skin, skin_type):
                        if element == 'image':
                            ordered_layers.append(f'{skin}.{skin_type}.{element}')
                        elif element == 'shadow':
                            ordered_layers.insert(0, f'{skin}.{skin_type}.{element}')
                else:
                    for layer in await Item.get_skin_layers(skin):
                        for element in await Item.get_skin_layer(skin, layer):
                            if element == 'image':
                                ordered_layers.append(f'{skin}.{layer}.{element}')
                            elif element == 'shadow':
                                ordered_layers.insert(0, f'{skin}.{layer}.{element}')
            ordered_layers = [[i] for i in ordered_layers]
            moved_layers = {}

            async def find_skin_type_from_ordered_layers_list(skin_type):
                for group in ordered_layers:
                    for skin in group:
                        layer_props = skin.split('.')
                        item_id = layer_props[0]
                        layer = layer_props[1]
                        type_ = layer_props[2]
                        if type_ == 'shadow':
                            continue
                        if layer in config.default_pig['skins'] and layer == skin_type:
                            return skin
                        elif await Item.get_skin_type(item_id) == skin_type:
                            return skin
                else:
                    for i in list(config.default_pig['skins'])[
                             :list(config.default_pig['skins']).index(skin_type)][::-1]:
                        for group in ordered_layers[::-1]:
                            skin = group[0]
                            layer_props = skin.split('.')
                            item_id = layer_props[0]
                            layer = layer_props[1]
                            if await Item.get_skin_type(item_id) == i or layer == i:
                                return skin

            def find_layer_in_grouped_layers(layer, return_index=True):
                for n, i in enumerate(ordered_layers):
                    if layer in i:
                        if return_index:
                            return n
                        else:
                            return i

            def has_common_elements_and_is_moved(g, m):
                res = {}
                for i in g:
                    if i in moved_layers:
                        if moved_layers[i] in m:
                            res[i] = moved_layers[i]
                return res

            left_eye_outline = None
            right_eye_outline = None
            right_ear_line = None
            while True:
                for group in ordered_layers.copy()[::-1]:
                    after_list = []
                    before_list = []

                    for skin in group:
                        layer_props = skin.split('.')
                        item_id = layer_props[0]
                        layer = layer_props[1]
                        type_ = layer_props[2]
                        if layer in config.default_pig['skins']:
                            skin_type = layer
                        else:
                            skin_type = await Item.get_skin_type(item_id)
                        if await Item.get_skin_right_ear_line_type(item_id) == '1' and right_ear_line in [None, 2]:
                            right_ear_line = '1'
                        elif await Item.get_skin_right_ear_line_type(item_id) == '2' and right_ear_line is None:
                            right_ear_line = '2'
                        if await Item.get_skin_right_eye_outline(item_id) is not None and right_eye_outline is None:
                            right_eye_outline = await Item.get_skin_right_eye_outline(item_id)
                        if await Item.get_skin_left_eye_outline(item_id) is not None and left_eye_outline is None:
                            left_eye_outline = await Item.get_skin_left_eye_outline(item_id)
                        if type_ == 'shadow':
                            continue
                        if await Item.get_skin_layer_before(item_id, layer) is not None:
                            before_list += [await Item.get_skin_layer_before(item_id, layer)] if isinstance(
                                await Item.get_skin_layer_before(item_id, layer), str) else await Item.get_skin_layer_before(
                                item_id,
                                layer)
                        if await Item.get_skin_layer_after(item_id, layer) is not None:
                            after_list += [await Item.get_skin_layer_after(item_id, layer)] if isinstance(
                                await Item.get_skin_layer_after(item_id, layer), str) else await Item.get_skin_layer_after(item_id,
                                                                                                               layer)
                        if skin_type in config.skin_layers_rules:
                            if 'before' in config.skin_layers_rules[skin_type]:
                                before_list += config.skin_layers_rules[skin_type]['before']
                            if 'after' in config.skin_layers_rules[skin_type]:
                                after_list += config.skin_layers_rules[skin_type]['after']
                    after_list = list(set(after_list))
                    before_list = list(set(before_list))
                    for i in group:
                        layer_props = i.split('.')
                        item_id = layer_props[0]
                        layer = layer_props[1]
                        if await Item.get_skin_type(item_id) in before_list:
                            before_list.remove(await Item.get_skin_type(item_id))
                        if layer in before_list:
                            before_list.remove(layer)
                        if await Item.get_skin_type(item_id) in after_list:
                            after_list.remove(await Item.get_skin_type(item_id))
                        if layer in after_list:
                            after_list.remove(layer)

                    skin = group[0]
                    if before_list:
                        layer_with_needed_before_type = None
                        for before in before_list:
                            layer_with_needed_before_type = await find_skin_type_from_ordered_layers_list(before)
                            if layer_with_needed_before_type is None:
                                continue
                            before_index = find_layer_in_grouped_layers(layer_with_needed_before_type)
                            if before_index < find_layer_in_grouped_layers(skin):
                                break
                        if layer_with_needed_before_type is None:
                            continue
                        if ordered_layers.index(group) == before_index:
                            continue
                        if before_index < find_layer_in_grouped_layers(skin):
                            ordered_layers[before_index] = ordered_layers.pop(ordered_layers.index(group)) + \
                                                           ordered_layers[before_index]
                            moved_layers[skin] = 'down'
                            break
                        elif has_common_elements_and_is_moved(group, ['up', 'pulled.up']):
                            ordered_layers[ordered_layers.index(group)] = ordered_layers[ordered_layers.index(
                                group)] + ordered_layers.pop(before_index)
                            moved_layers[layer_with_needed_before_type] = 'pulled.up'
                            break
                    if after_list:
                        layer_with_needed_after_type = None
                        for after in after_list:
                            layer_with_needed_after_type = await find_skin_type_from_ordered_layers_list(after)
                            if layer_with_needed_after_type is None:
                                continue
                            after_index = find_layer_in_grouped_layers(layer_with_needed_after_type)
                            if after_index > find_layer_in_grouped_layers(skin):
                                break
                        if layer_with_needed_after_type is None:
                            continue
                        if ordered_layers.index(group) == after_index:
                            continue
                        if after_index > find_layer_in_grouped_layers(skin):
                            if ordered_layers[after_index].index(layer_with_needed_after_type) not in [0,
                                                                                                       len(
                                                                                                           ordered_layers[
                                                                                                               after_index])]:
                                pass
                            elif has_common_elements_and_is_moved(group, ['down', 'pulled.down']):
                                ordered_layers[ordered_layers.index(group)] = ordered_layers.pop(after_index) + \
                                                                              ordered_layers[
                                                                                  ordered_layers.index(group)]
                                moved_layers[layer_with_needed_after_type] = 'pulled.down'
                                break
                            else:
                                new_group = ordered_layers[after_index] + ordered_layers.pop(
                                    ordered_layers.index(group))
                                ordered_layers[after_index - 1] = new_group
                                moved_layers[skin] = 'up'
                                break
                else:
                    break
            ordered_layers = [i for j in ordered_layers for i in j]
            new_ordered_layers = []
            for layer in ordered_layers:
                if await Item.get_skin_type(layer) in hide_skins or layer.split('.')[1] in hide_skins:
                    continue
                new_ordered_layers.append(layer)
            ordered_layers = new_ordered_layers
            final_pig_img = await Hidden.draw_pig_with_asyncio(tuple(ordered_layers),
                                                               left_eye_outline=left_eye_outline,
                                                               right_eye_outline=right_eye_outline,
                                                               right_ear_line=right_ear_line, eye_emotion=eye_emotion)
            output_path = Func.generate_temp_path('pig', file_extension='png')
            final_pig_img.save(output_path)
            if remove_transparency:
                return Hidden.remove_transparency(output_path)
            else:
                return output_path
        except Exception as e:
            raise

    @staticmethod
    async def draw_pig_with_asyncio(ordered_layers: tuple, left_eye_outline: str = None, right_eye_outline: str = None,
                                    right_ear_line: str = None, eye_emotion: str = None):
        ordered_layers = list(ordered_layers)
        copy_ordered_layers = ordered_layers.copy()
        separated_ordered_layers = []
        temp_list = []
        for layer in copy_ordered_layers.copy():
            layer_props = layer.split('.')
            if layer_props[-1] == 'shadow':
                temp_list.append(layer)
                copy_ordered_layers.remove(layer)
        separated_ordered_layers.append(temp_list)
        while True:
            separated_ordered_layers.append(copy_ordered_layers[:4])
            copy_ordered_layers = copy_ordered_layers[4:]
            if not copy_ordered_layers:
                break
        if [] in separated_ordered_layers:
            separated_ordered_layers.remove([])
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(separated_ordered_layers)) as executor:
            futures = [executor.submit(asyncio.run, Hidden.combine_pig_layers(i, left_eye_outline=left_eye_outline,
                                                                              right_eye_outline=right_eye_outline,
                                                                              right_ear_line=right_ear_line,
                                                                              return_as_path=False,
                                                                              eye_emotion=eye_emotion)) for i in
                       separated_ordered_layers]
            results = [future.result() for future in futures]
        return await Hidden.combine_images(tuple(results), return_as_path=False)

    @staticmethod
    async def combine_pig_layers(ordered_layers: tuple, left_eye_outline: str = None, right_eye_outline: str = None,
                                 right_ear_line: str = None, return_as_path=True, eye_emotion: str = None):
        ordered_layers = list(ordered_layers)
        pig_img = None

        async def fix_img_to_paste(img):
            if layer == 'right_ear' and type_ != 'shadow' and right_ear_line is not None:
                right_ear_img = Image.open(
                    await Func.get_image_path_from_link(await Item.get_skin_right_ear_line(item_id, right_ear_line)))
                img = Image.alpha_composite(img, right_ear_img)
            if layer == 'body' and left_eye_outline is not None:
                left_eye_outline_img = Image.open(await Func.get_image_path_from_link(left_eye_outline))
                right_eye_outline_img = Image.open(await Func.get_image_path_from_link(right_eye_outline))
                img = Image.alpha_composite(img, left_eye_outline_img)
                img = Image.alpha_composite(img, right_eye_outline_img)
            if layer in ['left_eye', 'right_eye']:
                if eye_emotion in config.emotions_erase_cords:
                    draw = ImageDraw.Draw(img)
                    for cords in config.emotions_erase_cords[eye_emotion]:
                        if len(cords) == 3:
                            x1 = cords[0] - cords[2]
                            y1 = cords[1] - cords[2]
                            x2 = cords[0] + cords[2]
                            y2 = cords[1] + cords[2]
                            draw.ellipse([(x1, y1), (x2, y2)], fill=img.getpixel((0, 0)))
                        else:
                            draw.polygon(cords, fill=img.getpixel((0, 0)))
            return img

        for i, skin in enumerate(ordered_layers):
            layer_props = skin.split('.')
            item_id = layer_props[0]
            layer = layer_props[1]
            type_ = layer_props[2]
            image_path = await Item.get_skin_layer_image_path(item_id, layer, type_)
            if pig_img is None and i == 0:
                pig_img = Image.open(image_path)
                pig_img = await fix_img_to_paste(pig_img)
                continue
            img_to_paste = Image.open(image_path)
            img_to_paste = await fix_img_to_paste(img_to_paste)
            pig_img = Image.alpha_composite(pig_img, img_to_paste)
        if return_as_path:
            output_path = Func.generate_temp_path('pig_part', file_extension='png')
            pig_img.save(output_path)
            return output_path
        return pig_img

    @staticmethod
    async def combine_images(images: tuple, output: str = None, return_as_path=True):
        images = list(images)
        if type(images[0]) == str:
            base_img = Image.open(images[0])
        else:
            base_img = images[0]
        for image in images[1:]:
            if type(image) == str:
                img_to_paste = Image.open(image)
            else:
                img_to_paste = image
            base_img = Image.alpha_composite(base_img, img_to_paste)
        if return_as_path:
            if output is None:
                output = Func.generate_temp_path('combined_image', file_extension='png')
            base_img.save(output)
            return output
        return base_img

    