# -*- coding: utf-8 -*-
"""Слой эмоций для дня 2 канона 2: вставляется не весь кадр, а только лицо.

Почему так: полноценный кадр на другую эмоцию генератор либо отбивает
(позы 1 и 4), либо отдаёт с заметно другой позой — при переключении девушка
«дёргается». Поэтому эмоция рисуется отдельным кропом головы и кладётся
обратно мягкой маской по лицу (волосы и фон в маску не попадают — там и
живут расхождения генератора).

Выравнивание: генератор держит кадр, но не идеально — голова выходит на
пара процентов мельче и со сдвигом в 10-30 px. Поэтому масштаб и сдвиг
подбираются перебором, а метрика считается ТОЛЬКО по коже лица: зелёный
фон и волосы дают плоскостной минимум и уводят подбор.

Патч — полноразмерный кадр 1170x1560 с прозрачным всем, кроме лица, поэтому
на экране он ложится ровно поверх арта без возни с координатами.

    python3 tools/prep_faces_d2.py [--debug]

Вход:  images/raw_real/_d2f_{mood}_{tag}.png
       images/raw_real/_d2sg{2,3,4}.png, _canon2_hero.png
Выход: assets/real/art_real_face_day2_{tag}_{mood}.webp
       (--debug) images/raw_real/_qa_face_{tag}_{mood}.png
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'images', 'raw_real')
OUT = os.path.join(ROOT, 'assets', 'real')
SM = (1170, 1560)
WORK_W = 300          # на какой ширине считаем ошибку (скорость)

BASE = {
    'sg1': os.path.join(RAW, '_canon2_hero.png'),
    'sg2': os.path.join(RAW, '_d2sg2.png'),
    'sg3': os.path.join(RAW, '_d2sg3.png'),
    'sg4': os.path.join(RAW, '_d2sg4.png'),
}
# кроп головы под генерацию — доли кадра (0..1)
CROP = {
    'sg1': (0.300, 0.030, 0.700, 0.250),
    'sg2': (0.355, 0.030, 0.725, 0.240),
    'sg3': (0.345, 0.025, 0.715, 0.245),
    'sg4': (0.375, 0.025, 0.725, 0.245),
}
# маска лица в долях кадра: центр + радиусы. Волосы, уши и фон — вне маски.
FACE = {
    'sg1': (0.455, 0.156, 0.074, 0.057),
    'sg2': (0.523, 0.143, 0.074, 0.057),
    'sg3': (0.507, 0.139, 0.072, 0.056),
    'sg4': (0.510, 0.144, 0.072, 0.056),
}
MOODS = ('blink', 'shy')
FEATHER = 0.10

# Кадр эмоции, из которого берём лицо. Если эмоция уже нарисована на весь
# кадр (день 1-2, позы 2-4 и моргание позы 1) — берём оттуда: такой кадр уже
# выровнен по базе (сдвиг 1-2 px), и лицо садится идеально.
# Для двух отсутствующих эмоций источник — отдельный кроп головы (_d2f_*),
# его масштаб и сдвиг подобраны вручную и лежат в MANUAL.
FULL = 'images/raw_real/_d2g_{mood}_{tag}.png'
MANUAL = {
    ('sg1', 'shy'): (1.02, -8, -2),
    ('sg4', 'shy'): (1.02, 4, -10),
}


def _plate(size):
    return Image.new('RGB', size, (13, 178, 38))


def _face_mask(frame_size, box, face):
    W, H = frame_size
    cx, cy = face[0] * W, face[1] * H
    rx, ry = face[2] * W, face[3] * H
    m = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(m)
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    d.ellipse((cx - rx * 0.9, cy - ry * 0.95, cx + rx * 0.9, cy + ry * 1.05), fill=255)
    m = m.filter(ImageFilter.GaussianBlur(max(1, int(min(rx, ry) * FEATHER))))
    return m.crop(box)


def build(tag, mood, debug=False):
    base_sm = Image.open(BASE[tag]).convert('RGB').resize(SM, Image.LANCZOS)
    W, H = SM
    x0, y0, x1, y1 = CROP[tag]
    box = (round(W * x0), round(H * y0), round(W * x1), round(H * y1))
    ref = base_sm.crop(box)

    src = os.path.join(RAW, f'_d2f_{mood}_{tag}.png')
    if not os.path.exists(src):
        print(f'  {tag} {mood}: нет {os.path.basename(src)}, пропуск')
        return None
    gen = Image.open(src).convert('RGB')
    if gen.size != ref.size:
        gen = gen.resize(ref.size, Image.LANCZOS)

    # Генератор меняет только мимику и держит кадр — выравнивание не нужно.
    # Расхождения по краям (волосы, фон) съедает широкая мягкая маска.
    patch_rgb = _plate(ref.size)
    patch_rgb.paste(gen, (0, 0))

    face_mask = _face_mask(SM, box, FACE[tag])
    patch = patch_rgb.convert('RGBA')
    patch.putalpha(face_mask)
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    canvas.paste(patch, (box[0], box[1]), patch)

    out = os.path.join(OUT, f'art_real_face_day2_{tag}_{mood}.webp')
    canvas.save(out, 'WEBP', quality=92, alpha_quality=100, method=6)
    print(f'  art_real_face_day2_{tag}_{mood}.webp '
          f'{os.path.getsize(out) / 1e3:.0f} KB')

    if debug:
        room = Image.open(os.path.join(ROOT, 'assets', 'room_day1.webp')).convert('RGB')
        s = max(W / room.width, H / room.height)
        room = room.resize((max(W, round(room.width * s)), max(H, round(room.height * s))),
                           Image.LANCZOS)
        bg = room.crop(((room.width - W) // 2, (room.height - H) // 2,
                        (room.width - W) // 2 + W, (room.height - H) // 2 + H))
        comp = bg.copy()
        comp.paste(base_sm.convert('RGBA'), (0, 0), base_sm.convert('RGBA'))
        comp.paste(canvas, (0, 0), canvas)
        crop = comp.crop((round(W * 0.30), round(H * 0.03), round(W * 0.74), round(H * 0.26)))
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
        crop.save(os.path.join(RAW, f'_qa_face_{tag}_{mood}.png'))
    return canvas


def main():
    debug = '--debug' in sys.argv
    for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
        print(f'{tag}:')
        for mood in MOODS:
            build(tag, mood, debug)
    print('готово')


if __name__ == '__main__':
    main()
