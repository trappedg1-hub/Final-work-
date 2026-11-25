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
MASTER = (1170, 1560)   # ровно разрешение арта, которое отдаётся телефону (_sm)

SRC = {
    '1': os.path.join(ROOT, 'assets', 'real', 'art_real_day1_{tag}_sm.webp'),
    '2': os.path.join(ROOT, 'assets', 'real', 'art_real_day2_{tag}_sm.webp'),
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
GEO = {}                 # key -> [left, top, width, height] в долях кадра
BAND_FEATHER = 0.22   # растушёвка полосы глаз
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
    wx0, wy0 = max(0, gx0 - int(ew * 0.9)), max(0, gy0 - int(eh * 1.2))
    wx1, wy1 = min(w, gx1 + int(ew * 0.9)), min(h, gy1 + int(eh * 1.2))
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


def match_low(gen, ref, radius=14.0, limit=9.0):
    """Низкочастотная подгонка яркости генерата под базовый кадр.

    Генератор иногда отдаёт лицо темнее (поза 2 дня 2 — заметно) — заплатка
    читается как тень. Правим только медленную составляющую и не больше
    +-limit уровней: иначе у волос появляется светлый ореол.
    """
    g = np.asarray(gen.convert('RGB')).astype(np.float32)
    r = np.asarray(ref.convert('RGB')).astype(np.float32)
    gb = cv2.GaussianBlur(g, (0, 0), radius)
    rb = cv2.GaussianBlur(r, (0, 0), radius)
    corr = np.clip(rb - gb, -limit, limit)
    out = np.clip(g + corr, 0, 255).astype('uint8')
    return Image.fromarray(out)


def match_sharp(gen, ref, region):
    """Подгонка резкости: генерат чётче базового арта (день 1 — мягкая рисовка).

    Иначе заплатка выглядит «вклеенной»: у неё зерно мельче, чем у кадра.
    """
    g = np.asarray(gen.convert('L')).astype(np.float32)
    r = np.asarray(ref.convert('L')).astype(np.float32)
    x0, y0, x1, y1 = [int(v) for v in region]
    vr = cv2.Laplacian(r[y0:y1, x0:x1], cv2.CV_32F).var()
    vg = cv2.Laplacian(g[y0:y1, x0:x1], cv2.CV_32F).var()
    if vg <= 0 or vr <= 0:
        return gen
    out = gen
    sigma = 0.6
    while vg > vr * 1.06 and sigma < 3.2:
        out = gen.filter(ImageFilter.GaussianBlur(sigma))
        vg = cv2.Laplacian(np.asarray(out.convert('L')).astype(np.float32), cv2.CV_32F).var()
        sigma += 0.4
    return out


def band_box(key, tw, th, pad=0.10):
    """Полоса обоих глаз в пикселях кропа: маска одна на всю пару.

    Две отдельные маски оставляли снаружи кусочек базового века — он читался
    как вторая ресница. Одна широкая полоса заменяет глазницу целиком.
    """
    bx = EYES[key]
    x0 = min(b[0] for b in bx) * tw
    x1 = max(b[2] for b in bx) * tw
    y0 = min(b[1] for b in bx) * th
    y1 = max(b[3] for b in bx) * th
    w, h = x1 - x0, y1 - y0
    return (x0 - pad * w * 0.5, y0 - h * 0.55, x1 + pad * w * 0.5, y1 + h * 0.55)


def _shift_band(ref, gen, box):
    """Сдвиг и масштаб по полосе глаз (шаблон = вся глазница целиком)."""
    a = np.asarray(ref.convert('L'), dtype=np.float32) / 255.0
    g0 = np.asarray(gen.convert('L'), dtype=np.float32) / 255.0
    x0, y0, x1, y1 = [int(v) for v in box]
    tpl = a[y0:y1, x0:x1]
    tw, th = tpl.shape[1], tpl.shape[0]
    mx_shift = int(tw * 0.22)
    my_shift = int(th * 0.55)
    best = (1.0, 0, 0, 0.0)
    for f in (0.96, 0.97, 0.98, 0.99, 1.0, 1.01, 1.02, 1.03, 1.04):
        g = cv2.resize(g0, None, fx=f, fy=f, interpolation=cv2.INTER_LANCZOS4)
        rx0, ry0 = max(0, x0 - mx_shift), max(0, y0 - my_shift)
        rx1, ry1 = min(g.shape[1], x1 + mx_shift), min(g.shape[0], y1 + my_shift)
        roi = g[ry0:ry1, rx0:rx1]
        if roi.shape[0] < th + 4 or roi.shape[1] < tw + 4:
            continue
        r = cv2.matchTemplate(roi, tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(r)
        if mx > best[3]:
            best = (f, x0 - (loc[0] + rx0), y0 - (loc[1] + ry0), mx)
    return best


def _nose_box(key, tw, th):
    """Область носа и фильтрума: единственная зона, которая НЕ меняется от мимики."""
    bx = EYES[key]
    x0 = min(b[0] for b in bx) * tw
    x1 = max(b[2] for b in bx) * tw
    y0 = max(b[3] for b in bx) * th
    eh = max((b[3] - b[1]) for b in bx) * th
    cx = (x0 + x1) / 2
    return (cx - (x1 - x0) * 0.34, y0 - eh * 0.10, cx + (x1 - x0) * 0.34, y0 + eh * 1.15)


def _shift_nose(ref, gen, box):
    """Сдвиг и масштаб генерата по носу (проверено глазами: лучше, чем (0,0))."""
    a = np.asarray(ref.convert('L'), dtype=np.float32) / 255.0
    x0, y0, x1, y1 = [int(v) for v in box]
    tpl = a[y0:y1, x0:x1]
    g0 = np.asarray(gen.convert('L'), dtype=np.float32) / 255.0
    best = (1.0, 0, 0, 0.0)
    for f in (0.96, 0.97, 0.98, 0.99, 1.0, 1.01, 1.02, 1.03, 1.04):
        g = cv2.resize(g0, None, fx=f, fy=f, interpolation=cv2.INTER_LANCZOS4)
        if g.shape[0] <= tpl.shape[0] or g.shape[1] <= tpl.shape[1]:
            continue
        r = cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(r)
        if mx > best[3]:
            best = (f, x0 - loc[0], y0 - loc[1], mx)
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
    gen = match_low(gen, ref)
    gen = match_sharp(gen, ref, _nose_box(key, tw, th))

    canvas = Image.new('RGBA', (tw, th), (0, 0, 0, 0))
    log = []
    B = band_box(key, tw, th)   # уже в пикселях кропа
    f, dx, dy, score = _shift_band(ref, gen, B)
    if score < 0.60:
        f, dx, dy = 1.0, 0, 0
    g2 = gen.resize((round(tw * f), round(th * f)), Image.LANCZOS) if f != 1.0 else gen
    log.append(f'{f:.2f}[{dx},{dy}]{score:.2f}')

    # Ядро — по каждому глазу почти в полную силу: иначе закрытые веки
    # ложатся поверх открытых с альфой ~0.4 и моргания не видно вообще.
    hard = Image.new('L', (tw, th), 0)
    dh = ImageDraw.Draw(hard)
    for b in EYES[key]:
        e = (b[0] * tw, b[1] * th, b[2] * tw, b[3] * th)
        cx, cy = (e[0] + e[2]) / 2, (e[1] + e[3]) / 2
        rx, ry = (e[2] - e[0]) / 2 * 1.12, (e[3] - e[1]) / 2 * 1.12
        dh.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    hard = hard.filter(ImageFilter.GaussianBlur(max(2, int(min(B[2] - B[0], B[3] - B[1]) * 0.06))))
    soft = Image.new('L', (tw, th), 0)
    ImageDraw.Draw(soft).ellipse(B, fill=255)
    soft = soft.filter(ImageFilter.GaussianBlur(max(3, int(min(B[2] - B[0], B[3] - B[1]) * BAND_FEATHER))))
    alpha = Image.fromarray(np.maximum(np.array(hard), (np.array(soft) * 0.85).astype('uint8')), 'L')

    if mood == 'shy':
        # щёки: кожа ровная — сюда можно класть содержимое генерата широко и мягко
        for b in EYES[key]:
            e = (b[0] * tw, b[1] * th, b[2] * tw, b[3] * th)
            ew, eh = (e[2] - e[0]), (e[3] - e[1])
            cx = (e[0] + e[2]) / 2
            cy = e[3] + eh * 0.55
            rx, ry = ew * 0.52 * CHEEK_GROW, eh * 0.62 * CHEEK_GROW
            m = _ell((tw, th), cx, cy, rx, ry, min(rx, ry) * CHEEK_FEATHER)
            alpha = Image.fromarray(np.maximum(np.array(alpha), np.array(m)), 'L')

    # ВАЖНО: RGB остаются «прямыми» (не умноженными на альфу). Раньше слои
    # склеивались через alpha_composite, PIL отдавал премноженный цвет — и
    # полупрозрачный край маски ложился на лицо серой тенью («квадрат»).
    # КАДР С ГЕНЕРАТОМ: в патч должен идти ИМЕННО он, а не базовый арт.
    # (Раньше здесь оставался неиспользованный буфер, и слой моргал «пустотой».)
    canvas_rgb = flat.copy()
    canvas_rgb.paste(g2, (box[0] + dx, box[1] + dy))

    # Кадр целиком отдавать вёрстке нельзя: элемент размером с кадр при
    # каждом моргании подсовывает телефону картинку на весь экран, а в
    # прозрачной зоне у неё чёрный цвет — при уменьшении это и давало серый
    # прямоугольник и тёмное лицо. Отдаём только область глаз: она маленькая,
    # в прозрачных пикселях лежит ЦВЕТ АРТА, а не чёрный.
    gx0 = (box[0] + B[0] - (B[2] - B[0]) * 0.22) / W
    gy0 = (box[1] + B[1] - (B[3] - B[1]) * 0.30) / H
    gx1 = (box[0] + B[2] + (B[2] - B[0]) * 0.22) / W
    gy1 = (box[1] + B[3] + (B[3] - B[1]) * 0.30) / H
    gx0, gy0 = max(0.0, gx0), max(0.0, gy0)
    gx1, gy1 = min(1.0, gx1), min(1.0, gy1)
    cbox = (round(W * gx0), round(H * gy0), round(W * gx1), round(H * gy1))
    full = canvas_rgb.crop(cbox).convert('RGBA')
    full_alpha = Image.new('L', full.size, 0)
    full_alpha.paste(alpha, (box[0] - cbox[0], box[1] - cbox[1]))
    full.putalpha(full_alpha)
    GEO[key] = [round(gx0, 4), round(gy0, 4), round(gx1 - gx0, 4), round(gy1 - gy0, 4)]
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
    import json
    with open(os.path.join(OUT, 'emo_geo.json'), 'w', encoding='utf-8') as fh:
        json.dump(GEO, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print('готово, геометрия в assets/real/emo_geo.json')


if __name__ == '__main__':
    main()
