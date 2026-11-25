# -*- coding: utf-8 -*-
"""Лёгкие версии кадров для телефона + маленький проп «грудь» с запечённой маской.

5K-мастера остаются в репозитории; в игру на телефоне отдаются _sm (srcset),
потому что 20-мегапиксельные текстуры + копия кадра под маску убивают FPS.
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, 'assets')

SM_SPRITE = (1170, 1560)     # 3:4
SM_ROOM = (1200, 1356)

CHEST_BOX = (0.22, 0.12, 0.78, 0.50)   # единый кроп для всех стадий (left, top, right, bottom)
CHEST_W = 720
# Грудь = ДВА отдельных пропа, по одному на каждую «округлость».
# (cx, cy, rx, ry) — контур груди в долях кадра спрайта: (левая, правая).
BUST = {
    'sg1': ((0.472, 0.378, 0.040, 0.034), (0.556, 0.375, 0.042, 0.034)),  # кофта
    'sg2': ((0.424, 0.370, 0.048, 0.045), (0.523, 0.368, 0.045, 0.045)),
    'sg3': ((0.442, 0.345, 0.063, 0.045), (0.586, 0.340, 0.065, 0.047)),  # топ
    'sg4': ((0.429, 0.404, 0.076, 0.074), (0.597, 0.397, 0.072, 0.075)),  # откинулась
}
SIDES = ('l', 'r')
CORE_K = 0.74    # непрозрачное ядро (доля контура груди)
HULL_K = 0.92    # внешняя граница растушёвки
HOLE_K = 0.68    # окно в базовом кадре — строго внутри ядра


def shrink(src, dest, size):
    im = Image.open(src).convert('RGBA')
    im.resize(size, Image.LANCZOS).save(dest, 'WEBP', quality=86, alpha_quality=98, method=6)
    print(f'{os.path.basename(dest)} {size} {os.path.getsize(dest)/1e6:.2f} MB')


def _ellipse_mask(size, cx, cy, rx, ry, k):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).ellipse([cx - rx*k, cy - ry*k, cx + rx*k, cy + ry*k], fill=255)
    return m


def _bust_mask(size, cx, cy, rx, ry):
    """Ядро + мягкая растушёвка наружу.

    Ядро непрозрачное — иначе край пропа полупрозрачный и сквозь него
    просвечивает окно в базовом кадре. Растушёвка гаснет у контура груди,
    поэтому нарисованный контур остаётся статичным: проп двигает только
    «мясо» внутри силуэта, и двойного контура не возникает.
    """
    hull = _ellipse_mask(size, cx, cy, rx, ry, HULL_K)
    hull = hull.filter(ImageFilter.GaussianBlur(max(2, int(min(rx, ry) * 0.085))))
    core = _ellipse_mask(size, cx, cy, rx, ry, CORE_K)
    return Image.fromarray(np.maximum(np.array(hull), np.array(core)))


def _hole_mask(size, cx, cy, rx, ry):
    m = _ellipse_mask(size, cx, cy, rx, ry, HOLE_K)
    return m.filter(ImageFilter.GaussianBlur(max(2, int(min(rx, ry) * 0.05))))


def _punch(path, tag, quality=90):
    im = Image.open(path).convert('RGBA')
    W, H = im.size
    hole = Image.new('L', (W, H), 0)
    for (cx, cy, rx, ry) in BUST[tag]:
        h = _hole_mask((W, H), cx * W, cy * H, rx * W, ry * H)
        hole = Image.fromarray(np.maximum(np.array(hole), np.array(h)))
    arr = np.array(im)
    arr[..., 3] = (arr[..., 3].astype(np.float32) * (1 - np.array(hole).astype(np.float32) / 255)).astype('uint8')
    Image.fromarray(arr, 'RGBA').save(path, 'WEBP', quality=quality, alpha_quality=100, method=6)
    print(f'окно: {os.path.basename(path)} {W}x{H} {os.path.getsize(path)/1e6:.2f} MB')


def punch_hole(tag):
    """Окно под каждой грудью в базовом кадре и в кадрах эмоций.

    Без него проп, уезжая, оставляет под собой старые пиксели — гостинг.
    """
    _punch(os.path.join(A, f'art_day1_{tag}.webp'), tag, 90)
    _punch(os.path.join(A, f'art_day1_{tag}_sm.webp'), tag, 86)
    for mood in ('blink', 'shy'):
        for suffix in ('', '_lg'):
            p = os.path.join(A, f'art_emo_{tag}_{mood}{suffix}.webp')
            if os.path.exists(p):
                _punch(p, tag, 88)


def chest_patch(tag):
    """Два маленьких пропа: левая и правая грудь (общий кроп, разная альфа)."""
    im = Image.open(os.path.join(A, f'art_day1_{tag}.webp')).convert('RGBA')
    W, H = im.size
    x0, y0, x1, y1 = CHEST_BOX
    box = (int(W*x0), int(H*y0), int(W*x1), int(H*y1))
    crop = im.crop(box)
    cw, ch = crop.size
    k = CHEST_W / cw
    crop = crop.resize((CHEST_W, max(1, round(ch*k))), Image.LANCZOS)
    mw, mh = CHEST_W, crop.height

    for side, (cx, cy, rx, ry) in zip(SIDES, BUST[tag]):
        mx = (cx - x0) / (x1 - x0) * mw
        my = (cy - y0) / (y1 - y0) * mh
        mrx = rx / (x1 - x0) * mw
        mry = ry / (y1 - y0) * mh
        mask = _bust_mask((mw, mh), mx, my, mrx, mry)
        arr = np.array(crop)
        arr[..., 3] = (np.array(mask).astype(np.float32) * (arr[..., 3].astype(np.float32)/255)).astype('uint8')
        out = os.path.join(A, f'chest_{tag}_{side}.webp')
        Image.fromarray(arr, 'RGBA').save(out, 'WEBP', quality=92, alpha_quality=100, method=6)
        print(f'chest_{tag}_{side}.webp {mw}x{mh} {os.path.getsize(out)/1e3:.0f} KB')


if __name__ == '__main__':
    only_chest = '--chest' in sys.argv
    only_sm = '--sm' in sys.argv
    if only_chest:
        for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
            chest_patch(tag)
            punch_hole(tag)
        sys.exit(0)
    for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
        shrink(os.path.join(A, f'art_day1_{tag}.webp'), os.path.join(A, f'art_day1_{tag}_sm.webp'), SM_SPRITE)
        chest_patch(tag)
    for name in ('room_day1', 'room_fg'):
        shrink(os.path.join(A, f'{name}.webp'), os.path.join(A, f'{name}_sm.webp'), SM_ROOM)
