# -*- coding: utf-8 -*-
"""Слой эмоций (лицо) для канона 2 — оба дня, в разрешении мастеров.

Эмоция рисуется отдельным кропом головы в 820 px, затем кладётся обратно
на кадр мягкой маской по лицу. Патч собирается в 2340x3120 — том же размере,
что и мастер арта, чтобы лицо не мылилось относительно тела.

Выравнивание: поиск шаблона по контурам (cv2). Генератор держит кадр, но
сдвигает голову на десятки пикселей; ищем в узком диапазоне (±34 px,
масштаб 0.97-1.03) и берём максимум корреляции по лицу.

    python3 tools/prep_faces_d2.py [--debug]

Вход:  images/raw_real/_d2f2_{mood}_{tag}.png  — день 2
       images/raw_real/_d1f2_{mood}_{tag}.png  — день 1
Выход: assets/real/art_real_face_day{1,2}_{tag}_{mood}.webp
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

# кроп головы в долях кадра — те же, по которым готовились кропы под генерацию
BOX = {
    '1sg1': (0.330, 0.012, 0.600, 0.158),
    '1sg2': (0.315, 0.012, 0.560, 0.155),
    '1sg3': (0.375, 0.010, 0.605, 0.158),
    '1sg4': (0.375, 0.010, 0.605, 0.158),
    '2sg1': (0.300, 0.030, 0.700, 0.250),
    '2sg2': (0.355, 0.030, 0.725, 0.240),
    '2sg3': (0.345, 0.025, 0.715, 0.245),
    '2sg4': (0.375, 0.025, 0.725, 0.245),
}
# маска лица в долях кадра (центр + радиусы): волосы и фон вне маски
FACE = {
    '1sg1': (0.462, 0.082, 0.055, 0.042),
    '1sg2': (0.432, 0.080, 0.052, 0.040),
    '1sg3': (0.487, 0.080, 0.052, 0.040),
    '1sg4': (0.487, 0.080, 0.052, 0.040),
    '2sg1': (0.455, 0.156, 0.074, 0.057),
    '2sg2': (0.523, 0.143, 0.074, 0.057),
    '2sg3': (0.507, 0.139, 0.072, 0.056),
    '2sg4': (0.510, 0.144, 0.072, 0.056),
}
MOODS = ('blink', 'shy')
FEATHER = 0.10


def _skin(arr):
    """Мягкая маска кожи: тёплые светлые пиксели (волосы и фон отсекаются)."""
    r, g, b = (arr[..., i].astype(np.float32) for i in range(3))
    warm = (r > 95) & (r > g + 6) & (g > b - 8)
    m = Image.fromarray((warm * 255).astype('uint8'), 'L').filter(ImageFilter.GaussianBlur(6))
    return np.asarray(m, dtype=np.float32) / 255.0


def _face_mask(box, face, flat_ref):
    """Маска лица: ядро по чертам + растушёвка строго по КОЖЕ.

    Раньше граница была эллипсом и проходила по волосам — сгенерированная
    прядь не совпадала с базовой, и на волосах проступала вторая дуга.
    Теперь маска гаснет на коже: волосы остаются от базового кадра.
    """
    W, H = MASTER
    cx, cy = face[0] * W, face[1] * H
    rx, ry = face[2] * W, face[3] * H
    ell = Image.new('L', (W, H), 0)
    d = ImageDraw.Draw(ell)
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=255)
    ell = np.asarray(ell, dtype=np.float32) / 255.0

    # ref — уже вырезанный кроп головы, поэтому считаем кожу на кадре целиком
    skin = _skin(np.asarray(flat_ref.convert('RGB')))
    # ядро — глаза/нос/губы: покрываем полностью, они не «кожа» по цвету
    core = Image.new('L', (W, H), 0)
    dc = ImageDraw.Draw(core)
    dc.ellipse((cx - rx * 0.72, cy - ry * 0.80, cx + rx * 0.72, cy + ry * 0.95), fill=255)
    core = np.asarray(core.filter(ImageFilter.GaussianBlur(10)), dtype=np.float32) / 255.0

    m = np.maximum(core, ell * skin)
    m = Image.fromarray((np.clip(m, 0, 1) * 255).astype('uint8'), 'L')
    m = m.filter(ImageFilter.GaussianBlur(max(3, int(min(rx, ry) * 0.06))))
    return m.crop(box)


def _align(ref, gen, face, box):
    """Сдвиг и масштаб лица: поиск шаблона по контурам внутри области лица."""
    ref_g = cv2.cvtColor(np.asarray(ref), cv2.COLOR_RGB2GRAY)
    gen_g = cv2.cvtColor(np.asarray(gen), cv2.COLOR_RGB2GRAY)
    h, w = ref_g.shape
    cx = face[0] * MASTER[0] - box[0]
    cy = face[1] * MASTER[1] - box[1]
    rx = face[2] * MASTER[0]
    ry = face[3] * MASTER[1]
    tx0, tx1 = int(cx - rx * 0.9), int(cx + rx * 0.9)
    ty0, ty1 = int(cy - ry * 0.95), int(cy + ry * 0.95)
    tx0, ty0 = max(0, tx0), max(0, ty0)
    tx1, ty1 = min(w, tx1), min(h, ty1)
    tpl_e = cv2.Canny(ref_g[ty0:ty1, tx0:tx1], 70, 170)
    best = None
    for f in (0.97, 0.98, 0.99, 1.0, 1.01, 1.02, 1.03):
        g = cv2.resize(gen_g, None, fx=f, fy=f, interpolation=cv2.INTER_LANCZOS4)
        if tpl_e.shape[0] >= g.shape[0] or tpl_e.shape[1] >= g.shape[1]:
            continue
        gx0, gy0 = max(0, tx0 - 34), max(0, ty0 - 34)
        gx1 = min(g.shape[1], tx1 + 34)
        gy1 = min(g.shape[0], ty1 + 34)
        roi = cv2.Canny(g, 70, 170)[gy0:gy1, gx0:gx1]
        if roi.shape[0] < tpl_e.shape[0] or roi.shape[1] < tpl_e.shape[1]:
            continue
        r = cv2.matchTemplate(roi, tpl_e, cv2.TM_CCOEFF_NORMED)
        _, mx, _, loc = cv2.minMaxLoc(r)
        if best is None or mx > best[0]:
            best = (mx, f, (loc[0] + gx0, loc[1] + gy0))
    if best is None:
        return 1.0, 0, 0
    _, f, (lx, ly) = best
    return f, tx0 - lx, ty0 - ly


def build(day, tag, mood, debug=False):
    key = f'{day}{tag}'
    W, H = MASTER
    art = Image.open(SRC[day].format(tag=tag)).convert('RGBA').resize(MASTER, Image.LANCZOS)
    flat = Image.new('RGB', MASTER, (13, 178, 38))
    flat.paste(art, (0, 0), art)

    x0, y0, x1, y1 = BOX[key]
    box = (round(W * x0), round(H * y0), round(W * x1), round(H * y1))
    ref = flat.crop(box)

    src = os.path.join(RAW, FACECROP[day].format(mood=mood, tag=tag))
    if not os.path.exists(src):
        print(f'  {key} {mood}: нет {os.path.basename(src)}, пропуск')
        return None
    gen = Image.open(src).convert('RGB')
    if gen.size != ref.size:
        gen = gen.resize(ref.size, Image.LANCZOS)

    f, dx, dy = _align(ref, gen, FACE[key], box)
    if abs(f - 1.0) > 1e-3:
        gen = gen.resize((round(gen.width * f), round(gen.height * f)), Image.LANCZOS)
    placed = Image.new('RGB', ref.size, (13, 178, 38))
    placed.paste(gen, (dx, dy))
    # лёгкая доводка резкости: кроп 820 px апскейлится в кадр мастера
    placed = placed.filter(ImageFilter.UnsharpMask(radius=2, percent=55, threshold=2))

    patch = placed.convert('RGBA')
    patch.putalpha(_face_mask(box, FACE[key], flat))
    canvas = Image.new('RGBA', MASTER, (0, 0, 0, 0))
    canvas.paste(patch, (box[0], box[1]), patch)

    out = os.path.join(OUT, f'art_real_face_day{day}_{tag}_{mood}.webp')
    canvas.save(out, 'WEBP', quality=90, alpha_quality=100, method=6)
    print(f'  art_real_face_day{day}_{tag}_{mood}.webp  x{f:.2f} [{dx},{dy}] '
          f'{os.path.getsize(out) / 1e3:.0f} KB')

    if debug:
        room = Image.open(os.path.join(ROOT, 'assets', 'room_day1.webp')).convert('RGB')
        s = max(W / room.width, H / room.height)
        room = room.resize((max(W, round(room.width * s)), max(H, round(room.height * s))), Image.LANCZOS)
        bg = room.crop(((room.width - W) // 2, (room.height - H) // 2,
                        (room.width - W) // 2 + W, (room.height - H) // 2 + H))
        comp = bg.copy()
        comp.paste(flat.convert('RGBA'), (0, 0), flat.convert('RGBA'))
        comp.paste(canvas, (0, 0), canvas)
        crop = comp.crop((round(W * (x0 - 0.02)), round(H * (y0 - 0.01)),
                          round(W * (x1 + 0.02)), round(H * (y1 + 0.05))))
        crop = crop.resize((round(crop.width * 0.55), round(crop.height * 0.55)), Image.LANCZOS)
        crop.save(os.path.join(RAW, f'_qa_face_{key}_{mood}.png'))
    return canvas


def main():
    debug = '--debug' in sys.argv
    for day in ('1', '2'):
        for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
            print(f'день {day} {tag}:')
            for mood in MOODS:
                build(day, tag, mood, debug)
    print('готово')


if __name__ == '__main__':
    main()
