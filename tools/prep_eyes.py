# -*- coding: utf-8 -*-
"""Эмоция = слой глаз и щёк, а не пятно лица.

Почему так: генератор меняет мимику, но голову слегка поворачивает и сдвигает
(на 30-60 px в кадре мастера). Любая маска «по лицу» ловит этот сдвиг и даёт
шов — светлую дугу по лбу и обрыв по щеке. Поэтому меняем только то, что
действительно изменилось:

* глаза — своя маска на каждый глаз, выравнивание по самому глазу;
* щёки — своя мягкая маска (там кожа ровная, шов невозможен).

Всё остальное — волосы, брови, нос, губы, фон — остаётся от базового кадра.

    python3 tools/prep_eyes.py [--debug]
"""
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'images', 'raw_real')
OUT = os.path.join(ROOT, 'assets', 'real')
MASTER = (2340, 3120)

SRC = {
    '1': os.path.join(ROOT, 'assets', 'real', 'art_real_day1_{tag}.webp'),
    '2': os.path.join(ROOT, 'assets', 'real', 'art_real_day2_{tag}.webp'),
}
FACECROP = {'1': '_d1f2_{mood}_{tag}.png', '2': '_d2f2_{mood}_{tag}.png'}

# кроп головы в долях кадра — тот же, по которому готовился кроп под генерацию
BOX = {
    '1sg1': (0.320, 0.010, 0.640, 0.240),
    '1sg2': (0.310, 0.010, 0.620, 0.235),
    '1sg3': (0.360, 0.008, 0.670, 0.238),
    '1sg4': (0.365, 0.008, 0.675, 0.238),
    '2sg1': (0.300, 0.030, 0.700, 0.250),
    '2sg2': (0.355, 0.030, 0.725, 0.240),
    '2sg3': (0.345, 0.025, 0.715, 0.245),
    '2sg4': (0.375, 0.025, 0.725, 0.245),
}
# глаза в долях КРОПА: (x0,y0,x1,y1) — левый по картинке, правый по картинке
EYES = {
    '1sg1': ((0.405, 0.575, 0.525, 0.685), (0.585, 0.545, 0.705, 0.655)),
    '1sg2': ((0.345, 0.545, 0.465, 0.655), (0.515, 0.495, 0.645, 0.605)),
    '1sg3': ((0.215, 0.555, 0.335, 0.665), (0.365, 0.485, 0.495, 0.595)),
    '1sg4': ((0.205, 0.575, 0.315, 0.675), (0.405, 0.505, 0.525, 0.605)),
    '2sg1': ((0.295, 0.455, 0.425, 0.565), (0.425, 0.385, 0.545, 0.495)),
    '2sg2': ((0.195, 0.745, 0.315, 0.835), (0.335, 0.595, 0.475, 0.705)),
    '2sg3': ((0.315, 0.475, 0.445, 0.565), (0.525, 0.415, 0.635, 0.505)),
    '2sg4': ((0.175, 0.555, 0.295, 0.645), (0.325, 0.455, 0.465, 0.545)),
}
MOODS = ('blink', 'shy')
EYE_GROW = 1.22        # маска глаза: сам глаз + уголки, не залезая на бровь
EYE_FEATHER = 0.40
CHEEK_GROW = 1.15      # щёки — в долях глаза
CHEEK_FEATHER = 0.60


def _g(img):
    return cv2.cvtColor(np.asarray(img.convert('RGB')), cv2.COLOR_RGB2GRAY)


def _shift(ref, gen, b):
    """Сдвиг и масштаб по одному глазу: корреляция внутри окна вокруг глаза."""
    rx, ry = _g(ref), _g(gen)
    h, w = rx.shape
    gx0, gy0, gx1, gy1 = int(b[0]), int(b[1]), int(b[2]), int(b[3])
    ew, eh = gx1 - gx0, gy1 - gy0
    wx0, wy0 = max(0, gx0 - ew), max(0, gy0 - eh)
    wx1, wy1 = min(w, gx1 + ew), min(h, gy1 + eh)
    tpl = rx[gy0:gy1, gx0:gx1]
    best = (1.0, 0, 0, -1.0)
    for f in (0.94, 0.96, 0.98, 1.0, 1.02, 1.04, 1.06):
        g2 = cv2.resize(ry, None, fx=f, fy=f, interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_LANCZOS4)
        rx0, ry0 = max(0, wx0 - 20), max(0, wy0 - 20)
        rx1, ry1 = min(g2.shape[1], wx1 + 20), min(g2.shape[0], wy1 + 20)
        roi = g2[ry0:ry1, rx0:rx1]
        if roi.shape[0] < tpl.shape[0] or roi.shape[1] < tpl.shape[1]:
            continue
        res = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(res)
        if mx > best[3]:
            best = (f, gx0 - (loc[0] + rx0), gy0 - (loc[1] + ry0), mx)
    return best


def _ell(size, cx, cy, rx, ry, blur):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    return m.filter(ImageFilter.GaussianBlur(max(2, int(blur))))


def build(day, tag, mood, debug=False):
    key = f'{day}{tag}'
    W, H = MASTER
    art = Image.open(SRC[day].format(tag=tag)).convert('RGBA').resize(MASTER, Image.LANCZOS)
    flat = Image.new('RGB', MASTER, (13, 178, 38))
    flat.paste(art, (0, 0), art)

    bx = BOX[key]
    box = (round(W * bx[0]), round(H * bx[1]), round(W * bx[2]), round(H * bx[3]))
    ref = flat.crop(box)
    tw, th = ref.size

    src = os.path.join(RAW, FACECROP[day].format(mood=mood, tag=tag))
    if not os.path.exists(src):
        print(f'  {key} {mood}: нет {os.path.basename(src)}')
        return None
    gen = Image.open(src).convert('RGB').resize((tw, th), Image.LANCZOS)
    # генерат мягче базового арта (820 px -> кроп кадра): возвращаем ту же резкость,
    # иначе под маской видна «замыленная» кожа
    gen = gen.filter(ImageFilter.UnsharpMask(radius=1.6, percent=70, threshold=2))

    canvas = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    log = []
    for b in EYES[key]:
        e = (b[0] * tw, b[1] * th, b[2] * tw, b[3] * th)
        # вставка строго в (0,0): кадр у генератора тот же, а любой автоподбор
        # сдвига по закрытому глазу уводил мимику в сторону (проверено на 2sg2/2sg3)
        dx = dy = 0
        log.append('в (0,0)')
        cx, cy = (e[0] + e[2]) / 2, (e[1] + e[3]) / 2
        rx, ry = (e[2] - e[0]) / 2 * EYE_GROW, (e[3] - e[1]) / 2 * EYE_GROW * 1.15
        # центр маски выше середины глаза: иначе верхнее веко базового кадра
        # остаётся снаружи маски и рядом с новой линией читается как вторая ресница
        cy -= ry * 0.10
        m = _ell((tw, th), cx, cy, rx, max(ry, rx * 0.40), min(rx, ry) * EYE_FEATHER)
        layer = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
        layer.paste(gen, (0, 0))
        layer.putalpha(m)
        canvas.alpha_composite(layer)

    if mood == 'shy':
        # щёки: кожа ровная — сюда можно класть содержимое генерата широко и мягко
        for b in EYES[key]:
            e = (b[0] * tw, b[1] * th, b[2] * tw, b[3] * th)
            ew, eh = (e[2] - e[0]), (e[3] - e[1])
            cx = (e[0] + e[2]) / 2
            cy = e[3] + eh * 0.55
            rx, ry = ew * 0.52 * CHEEK_GROW, eh * 0.62 * CHEEK_GROW
            m = _ell((tw, th), cx, cy, rx, ry, min(rx, ry) * CHEEK_FEATHER)
            layer = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
            layer.paste(gen, (0, 0))
            layer.putalpha(m)
            canvas.alpha_composite(layer)

    full = Image.new('RGBA', MASTER, (0, 0, 0, 0))
    full.paste(canvas, (box[0], box[1]), canvas)
    out = os.path.join(OUT, f'art_real_face_day{day}_{tag}_{mood}.webp')
    full.save(out, 'WEBP', quality=92, alpha_quality=100, method=6)
    print(f'  art_real_face_day{day}_{tag}_{mood}.webp  ' + ' '.join(log) +
          f'  {os.path.getsize(out) / 1e3:.0f} KB')

    if debug:
        room = Image.open(os.path.join(ROOT, 'assets', 'room_day1.webp')).convert('RGB')
        s = max(W / room.width, H / room.height)
        room = room.resize((max(W, round(room.width * s)), max(H, round(room.height * s))), Image.LANCZOS)
        bg = room.crop(((room.width - W) // 2, (room.height - H) // 2,
                        (room.width - W) // 2 + W, (room.height - H) // 2 + H))
        comp = bg.copy()
        comp.paste(flat.convert('RGBA'), (0, 0), flat.convert('RGBA'))
        comp.paste(full, (0, 0), full)
        xs = [b[0] for b in EYES[key]] + [b[2] for b in EYES[key]]
        ys = [b[1] for b in EYES[key]] + [b[3] for b in EYES[key]]
        pad = 0.10
        q = comp.crop((round(box[0] + min(xs) * tw - pad * tw), round(box[1] + min(ys) * th - pad * th),
                       round(box[0] + max(xs) * tw + pad * tw), round(box[1] + max(ys) * th + pad * th * 1.4)))
        q = q.resize((round(q.width * 1.1), round(q.height * 1.1)), Image.LANCZOS)
        q.save(os.path.join(RAW, f'_qa_eyes_{key}_{mood}.png'))
    return full


def main():
    debug = '--debug' in sys.argv
    for day in ('1', '2'):
        for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
            for mood in MOODS:
                build(day, tag, mood, debug)
    print('готово')


if __name__ == '__main__':
    main()
