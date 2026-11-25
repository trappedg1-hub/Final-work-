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
from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'images', 'raw_real')
OUT = os.path.join(ROOT, 'assets', 'real')
MASTER = (1170, 1560)   # ровно разрешение арта, которое отдаётся телефону (_sm)

SRC = {
    '1': os.path.join(ROOT, 'assets', 'real', 'art_real_day1_{tag}_sm.webp'),
    '2': os.path.join(ROOT, 'assets', 'real', 'art_real_day2_{tag}_sm.webp'),
    '3': os.path.join(ROOT, 'assets', 'real', 'art_real_day3_{tag}_sm.webp'),
}
FACECROP = {'1': '_d1f2_{mood}_{tag}.png', '2': '_d2f2_{mood}_{tag}.png',
            '3': '_d3f2_{mood}_{tag}.png'}

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
    '3sg1': (0.520, 0.060, 0.860, 0.300),
    '3sg2': (0.050, 0.100, 0.360, 0.330),
    '3sg3': (0.360, 0.040, 0.660, 0.270),
    '3sg4': (0.440, 0.020, 0.760, 0.260),
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
    '3sg1': ((0.290, 0.430, 0.440, 0.560), (0.470, 0.570, 0.620, 0.700)),
    '3sg2': ((0.360, 0.600, 0.500, 0.720), (0.545, 0.490, 0.680, 0.610)),
    '3sg3': ((0.350, 0.530, 0.485, 0.640), (0.600, 0.510, 0.725, 0.620)),
    '3sg4': ((0.235, 0.462, 0.375, 0.565), (0.415, 0.535, 0.555, 0.638)),
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
    """Сдвиг и масштаб по полосе глаз (шаблон = вся глазница целиком).

    Ищем по КОНТУРАМ и в широком диапазоне: генератор иногда отдаёт голову
    заметно мельче и сдвинутой (2-й день, 2-я стадия — масштаб ~0.90). Старый
    узкий диапазон 0.96..1.04 давал «совпадение» с плохим выравниванием, и веко
    ложилось мимо глаза — два глаза друг на друге.
    """
    def edges(x):
        g = cv2.GaussianBlur(x, (0, 0), 1.2)
        gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
        e = np.abs(gx) + np.abs(gy)
        return cv2.GaussianBlur(e, (0, 0), 1.0)

    a = edges(np.asarray(ref.convert('L'), dtype=np.float32))
    g0 = edges(np.asarray(gen.convert('L'), dtype=np.float32))
    x0, y0, x1, y1 = [int(v) for v in box]
    tpl = a[y0:y1, x0:x1]
    if tpl.shape[0] < 8 or tpl.shape[1] < 8:
        return (1.0, 0, 0, 0.0)
    best = (1.0, 0, 0, -1.0)
    for f in [0.82 + 0.02 * i for i in range(19)]:
        g = cv2.resize(g0, None, fx=f, fy=f, interpolation=cv2.INTER_AREA if f < 1 else cv2.INTER_LANCZOS4)
        if g.shape[0] < tpl.shape[0] or g.shape[1] < tpl.shape[1]:
            continue
        r = cv2.matchTemplate(g, tpl, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(r)
        if mx > best[3]:
            best = (f, x0 - loc[0], y0 - loc[1], mx)
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
    if score < 0.45:
        f, dx, dy = 1.0, 0, 0
    g2 = gen.resize((round(tw * f), round(th * f)), Image.LANCZOS) if f != 1.0 else gen
    log.append(f'{f:.2f}[{dx},{dy}]{score:.2f}')

    # Ядро — по каждому глазу почти в полную силу: иначе закрытые веки
    # ложатся поверх открытых с альфой ~0.4 и моргания не видно вообще.
    hard = Image.new('L', (tw, th), 0)
    dh = ImageDraw.Draw(hard)
    for b in EYES[key]:
        e = (b[0] * tw, b[1] * th, b[2] * tw, b[3] * th)
        ew_, eh_ = e[2] - e[0], e[3] - e[1]
        # Низ расширяем: под глазом остаётся тёмная линия нижних ресниц, и в
        # растушёвке она просвечивала чёрными точками на закрытом веке.
        dh.rectangle([e[0] - ew_ * 0.22, e[1] - eh_ * 0.06,
                      e[2] + ew_ * 0.22, e[3] + eh_ * 0.45], fill=255)
    # кромку ядра растушёвываем сильнее: при 2 px на коже была видна прямая
    # граница прямоугольника («стеклянная плашка» над глазом)
    hard = hard.filter(ImageFilter.GaussianBlur(5))
    # Растушёвка — ВОКРУГ КАЖДОГО ГЛАЗА, а не общим овалом на всю полосу:
    # у наклонённой головы в полосу попадает бровь, и её смещённая копия из
    # генерата ложилась второй дугой над веком.
    soft = Image.new('L', (tw, th), 0)
    ds = ImageDraw.Draw(soft)
    for b in EYES[key]:
        e = (b[0] * tw, b[1] * th, b[2] * tw, b[3] * th)
        cx, cy = (e[0] + e[2]) / 2, (e[1] + e[3]) / 2
        rx, ry = (e[2] - e[0]) / 2 * 1.70, (e[3] - e[1]) / 2 * 1.55
        ds.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    soft = soft.filter(ImageFilter.GaussianBlur(max(3, int(min(B[2] - B[0], B[3] - B[1]) * 0.09))))
    alpha = Image.fromarray(np.maximum(np.array(hard), (np.array(soft) * 0.50).astype('uint8')), 'L')

    # Гарантия «старого глаза не видно»: там, где в арте лежит тёмный зрачок,
    # ресницы или зелёная радужка, альфа — полная. Иначе у наклонённого глаза
    # (2-й день, 2-я стадия) старый зрачок просвечивал рядом с новым веком и
    # получалось два глаза друг на друге.
    ra_ = np.asarray(ref.convert('RGB')).astype(np.float32)
    lum_ = ra_.mean(axis=2)
    grn_ = (ra_[..., 1] > ra_[..., 0] + 4) & (ra_[..., 1] > ra_[..., 2] + 4)
    eye_px = ((lum_ < 118) | grn_).astype('uint8') * 255
    box_only = np.zeros((th, tw), dtype='uint8')
    for b in EYES[key]:
        e = (b[0] * tw, b[1] * th, b[2] * tw, b[3] * th)
        ew_, eh_ = e[2] - e[0], e[3] - e[1]
        cv2.rectangle(box_only, (int(e[0] - ew_ * 0.30), int(e[1] - eh_ * 0.10)),
                      (int(e[2] + ew_ * 0.30), int(e[3] + eh_ * 0.50)), 255, -1)
    eye_px = cv2.bitwise_and(eye_px, box_only)
    eye_px = cv2.dilate(eye_px, np.ones((5, 5), 'uint8'))
    eye_px = cv2.GaussianBlur(eye_px, (0, 0), 1.6)
    alpha = Image.fromarray(np.maximum(np.array(alpha), eye_px), 'L')

    # Выше верхней кромки бокса глаза альфу обнуляем: там бровь. Иначе её
    # смещённая копия из генерата ложилась второй дугой над веком.
    al_np = np.asarray(alpha).astype(np.float32).copy()
    for b in EYES[key]:
        e = (b[0] * tw, b[1] * th, b[2] * tw, b[3] * th)
        top = e[1] - 2.0
        xs0, xs1 = int(e[0] - (e[2] - e[0]) * 0.30), int(e[2] + (e[2] - e[0]) * 0.30)
        xs0, xs1 = max(0, xs0), min(tw, xs1)
        yy = np.arange(th, dtype=np.float32)[:, None]
        ramp = np.clip((yy - (top - 6.0)) / 6.0, 0.0, 1.0)
        xx = np.arange(tw, dtype=np.float32)[None, :]
        # по X — тоже плавно, иначе на стыке полосы появляется вертикальная
        # линия («стеклянная плашка» над глазом)
        xw = np.clip(np.minimum((xx - xs0) / 9.0, (xs1 - xx) / 9.0), 0.0, 1.0)
        al_np *= (1.0 - (1.0 - ramp) * xw)
    alpha = Image.fromarray(al_np.astype('uint8'), 'L')

    if mood == 'shy':
        # Щёки: «вниз по лицу», а не «вниз по кадру». У наклонённой головы
        # (2-й день, 2-я стадия) смещение по Y уводило щёку на соседний глаз, и
        # поверх него ложилось второе веко — «эмоции друг на друге».
        e0 = [b * v for b, v in zip(EYES[key][0], (tw, th, tw, th))]
        e1 = [b * v for b, v in zip(EYES[key][-1], (tw, th, tw, th))]
        ux, uy = (e1[0] + e1[2]) / 2 - (e0[0] + e0[2]) / 2, (e1[1] + e1[3]) / 2 - (e0[1] + e0[3]) / 2
        n = max(1e-6, (ux * ux + uy * uy) ** 0.5)
        ux, uy = ux / n, uy / n
        down = (-uy, ux) if ux >= 0 else (uy, -ux)      # перпендикуляр к линии глаз, вниз
        for b in EYES[key]:
            e = (b[0] * tw, b[1] * th, b[2] * tw, b[3] * th)
            ew, eh = (e[2] - e[0]), (e[3] - e[1])
            cx = (e[0] + e[2]) / 2 + down[0] * eh * 0.95
            cy = (e[1] + e[3]) / 2 + down[1] * eh * 0.95
            rx, ry = ew * 0.52 * CHEEK_GROW, eh * 0.62 * CHEEK_GROW
            m = _ell((tw, th), cx, cy, rx, ry, min(rx, ry) * CHEEK_FEATHER)
            alpha = Image.fromarray(np.maximum(np.array(alpha), np.array(m)), 'L')

    # ВАЖНО: RGB остаются «прямыми» (не умноженными на альфу). Раньше слои
    # склеивались через alpha_composite, PIL отдавал премноженный цвет — и
    # полупрозрачный край маски ложился на лицо серой тенью («квадрат»).
    # КАДР С ГЕНЕРАТОМ: в патч должен идти ИМЕННО он, а не базовый арт.
    # (Раньше здесь оставался неиспользованный буфер, и слой моргал «пустотой».)
    # Гасим НИЗКОЧАСТОТНУЮ ошибку генерата: он перерисовывает лицо чуть иначе
    # по свету и гладкости, и в полупрозрачной растушёвке это читалось как
    # «два лица друг на друге» (особенно на наклонённой голове, 2-й день,
    # 2-я стадия). Оставляем от генерата только локальную деталь — веки.
    gg = g2 if g2.size == ref.size else g2.resize(ref.size, Image.LANCZOS)
    ra = np.asarray(ref.convert('RGB'), dtype=np.float32)
    ga = np.asarray(gg.convert('RGB'), dtype=np.float32)
    sig = max(2.5, min(ref.size) * 0.045)
    # Поправку ограничиваем: у сильных контрастов (кромка волос над глазом)
    # размытая разница уходила в десятки уровней и вычиталась из патча —
    # на полупрозрачном крае маски это читалось как ЧЁРНЫЕ ПЯТНЫШКИ на лице.
    low = np.clip(cv2.GaussianBlur(ga - ra, (0, 0), sig), -12.0, 12.0)
    g2c = Image.fromarray(np.clip(ga - low, 0, 255).astype('uint8'), 'RGB')
    canvas_rgb = flat.copy()
    canvas_rgb.paste(g2c, (box[0] + dx, box[1] + dy))

    canvas_rgb = flat.copy()
    canvas_rgb.paste(g2c, (box[0] + dx, box[1] + dy))

    if mood == 'shy':
        # ГЛАЗА ДЛЯ «shy» БЕРЁМ ИЗ «blink». У наклонённых поз (2-й день, 2-я
        # стадия) генерат «shy» рисует затенённый глаз выше и мельче, чем в
        # арте, и поверх старого глаза ложится второе веко — «эмоции друг на
        # друге». Моргание выровнено идеально, поэтому веки берём оттуда, а от
        # «shy» остаётся румянец.
        srcb = os.path.join(RAW, FACECROP[day].format(mood='blink', tag=tag))
        if os.path.exists(srcb):
            genb = Image.open(srcb).convert('RGB').resize((tw, th), Image.LANCZOS)
            genb = match_sharp(match_low(genb, ref), ref, _nose_box(key, tw, th))
            fb, dxb, dyb, sb = _shift_band(ref, genb, B)
            if sb < 0.45:
                fb, dxb, dyb = 1.0, 0, 0
            gb2 = genb.resize((round(tw * fb), round(th * fb)), Image.LANCZOS) if fb != 1.0 else genb
            ggb = gb2 if gb2.size == ref.size else gb2.resize(ref.size, Image.LANCZOS)
            rab = np.asarray(ref.convert('RGB'), dtype=np.float32)
            gbb = np.asarray(ggb.convert('RGB'), dtype=np.float32)
            lowb = np.clip(cv2.GaussianBlur(gbb - rab, (0, 0), sig), -12.0, 12.0)
            gbc = Image.fromarray(np.clip(gbb - lowb, 0, 255).astype('uint8'), 'RGB')
            canvas_b = flat.copy()
            canvas_b.paste(gbc, (box[0] + dxb, box[1] + dyb))
            m_eye = Image.new('L', MASTER, 0)
            dm = ImageDraw.Draw(m_eye)
            for b in EYES[key]:
                e = (b[0] * tw, b[1] * th, b[2] * tw, b[3] * th)
                ex, ey = (e[2] - e[0]) * 0.16, (e[3] - e[1]) * 0.16
                dm.rectangle([box[0] + e[0] - ex, box[1] + e[1] - ey,
                              box[0] + e[2] + ex, box[1] + e[3] + ey], fill=255)
            m_eye = m_eye.filter(ImageFilter.GaussianBlur(3))
            canvas_rgb = Image.composite(canvas_b, canvas_rgb, m_eye)

    # Кадр целиком отдавать вёрстке нельзя: элемент размером с кадр при
    # каждом моргании подсовывает телефону картинку на весь экран, а в
    # прозрачной зоне у неё чёрный цвет — при уменьшении это и давало серый
    # прямоугольник и тёмное лицо. Отдаём только область глаз: она маленькая,
    # в прозрачных пикселях лежит ЦВЕТ АРТА, а не чёрный.
    # Запас по краям минимальный: сгенерированный кадр — это перерисовка всего
    # лица, и чем дальше от глаз, тем сильнее она «уезжает» от арта. С большим
    # запасом на наклонённом лице (2-й день, 2-я поза) видно ДВА лица друг на
    # друге — нос и контур щеки в генерате стоят иначе.
    gx0 = (box[0] + B[0] - (B[2] - B[0]) * 0.05) / W
    gy0 = (box[1] + B[1] - (B[3] - B[1]) * 0.10) / H
    gx1 = (box[0] + B[2] + (B[2] - B[0]) * 0.05) / W
    gy1 = (box[1] + B[3] + (B[3] - B[1]) * 0.10) / H
    gx0, gy0 = max(0.0, gx0), max(0.0, gy0)
    gx1, gy1 = min(1.0, gx1), min(1.0, gy1)
    cbox = (round(W * gx0), round(H * gy0), round(W * gx1), round(H * gy1))
    full = canvas_rgb.crop(cbox).convert('RGBA')
    full_alpha = Image.new('L', full.size, 0)
    full_alpha.paste(alpha, (box[0] - cbox[0], box[1] - cbox[1]))
    # Альфа обязана дойти до нуля у самой кромки: иначе на границе кропа
    # остаётся прямая линия и патч читается как прямоугольник поверх лица.
    win = Image.new('L', full.size, 0)
    mx, my = max(2, int(full.width * 0.10)), max(2, int(full.height * 0.10))
    ImageDraw.Draw(win).rounded_rectangle(
        [mx, my, full.width - 1 - mx, full.height - 1 - my],
        radius=int(min(full.size) * 0.26), fill=255)
    win = win.filter(ImageFilter.GaussianBlur(max(2, int(min(full.size) * 0.07))))
    full_alpha = ImageChops.multiply(full_alpha, win)
    full.putalpha(full_alpha)

    # На ПОЛУПРОЗРАЧНОЙ кромке не должно быть структуры (ресниц, брови): там
    # содержимое генерата смещено на пару пикселей и читается как чёрные
    # пятнышки на коже. Поэтому на краю патч не темнее арта больше чем на 28
    # уровней — остаются только плавные переходы (румянец, тени).
    arr_ = np.asarray(full).astype(np.float32)
    art_c = np.asarray(flat.crop(cbox).convert('RGB'), dtype=np.float32)
    al_ = arr_[..., 3:4] / 255.0
    low_mask = al_ < 0.86
    arr_[..., :3] = np.where(low_mask, np.maximum(arr_[..., :3], art_c - 28.0), arr_[..., :3])
    full = Image.fromarray(np.clip(arr_, 0, 255).astype('uint8'), 'RGBA')

    # Точечная чистка: одиночные тёмные точки (след смещённой ресницы/тени)
    # заменяем медианой окружения. Линии (само веко) медиана сохраняет,
    # поэтому структура не страдает — исчезают именно «пятнышки».
    arr2_ = np.asarray(full).astype(np.float32)
    rgb_im = full.convert('RGB')
    med_ = np.asarray(rgb_im.filter(ImageFilter.MedianFilter(5)), dtype=np.float32)
    lum_ = arr2_[..., :3].mean(axis=2)
    lmed_ = med_.mean(axis=2)
    artl_ = art_c.mean(axis=2)
    spot_ = (lum_ < artl_ - 22.0) & (lmed_ > lum_ + 10.0) & (arr2_[..., 3] > 90)
    if spot_.any():
        arr2_[..., :3] = np.where(spot_[..., None], med_, arr2_[..., :3])
        full = Image.fromarray(np.clip(arr2_, 0, 255).astype('uint8'), 'RGBA')
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
    import json
    debug = '--debug' in sys.argv
    days = ('1', '2', '3')
    if '--day' in sys.argv:
        days = (sys.argv[sys.argv.index('--day') + 1],)
    geo_path = os.path.join(OUT, 'emo_geo.json')
    # гео остальных дней не теряем: пишем только пересчитанные ключи
    if os.path.exists(geo_path):
        with open(geo_path, encoding='utf-8') as fh:
            GEO.update(json.load(fh))
    for day in days:
        for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
            for mood in MOODS:
                build(day, tag, mood, debug)
    with open(geo_path, 'w', encoding='utf-8') as fh:
        json.dump(GEO, fh, ensure_ascii=False, indent=1, sort_keys=True)
    print('готово, геометрия в assets/real/emo_geo.json')


if __name__ == '__main__':
    main()
