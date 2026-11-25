# -*- coding: utf-8 -*-
"""Пропы груди и окна под ними для реалистичной версии (канон 2).

Логика та же, что в prep_light.py (ядро 0.52 / hull 0.66, окно меньше ядра на
ход пружины), меняются только имена файлов и BUST для реалистичных поз.

Порядок обязателен: сначала chest_patch (читает целый _sm), потом punch_hole.
Повторный запуск на уже пробитых кадрах удвоит прокол — гонять только от чистых.

Usage:  python3 tools/prep_real_chest.py
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_light as PL  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, 'assets', 'real')

CHEST_BOX = PL.CHEST_BOX
SIDES = PL.SIDES

# (cx, cy, rx, ry) в долях кадра спрайта — снято по мелкой сетке на кадрах канона 2
BUST_REAL = {
    'sg1': ((0.466, 0.352, 0.040, 0.044), (0.570, 0.344, 0.056, 0.046)),  # худи, рука у подбородка
    'sg2': ((0.480, 0.344, 0.043, 0.046), (0.568, 0.336, 0.052, 0.048)),  # худи расстёгнуто
    'sg3': ((0.460, 0.322, 0.042, 0.040), (0.572, 0.316, 0.045, 0.042)),  # топ, нога поднята
    'sg4': ((0.464, 0.328, 0.046, 0.042), (0.574, 0.322, 0.050, 0.044)),  # топ, колени обняла
}


def _sm(tag):
    return os.path.join(A, f'art_real_day1_{tag}_sm.webp')


def _master(tag):
    return os.path.join(A, f'art_real_day1_{tag}.webp')


def chest_patch(tag):
    """Два пропа (левая/правая) — кроп из _sm без масштабирования."""
    im = Image.open(_sm(tag)).convert('RGBA')
    W, H = im.size
    x0, y0, x1, y1 = CHEST_BOX
    crop = im.crop((int(W * x0), int(H * y0), int(W * x1), int(H * y1)))
    mw, mh = crop.size

    for side, (cx, cy, rx, ry) in zip(SIDES, BUST_REAL[tag]):
        mx = (cx - x0) / (x1 - x0) * mw
        my = (cy - y0) / (y1 - y0) * mh
        mrx = rx / (x1 - x0) * mw
        mry = ry / (y1 - y0) * mh
        mask = PL._bulge_mask((mw, mh), mx, my, mrx, mry)
        arr = np.array(crop)
        arr[..., 3] = (np.array(mask).astype(np.float32) * (arr[..., 3].astype(np.float32) / 255)).astype('uint8')
        rgb = Image.fromarray(arr[..., :3].astype('uint8')).filter(ImageFilter.GaussianBlur(9))
        arr[..., :3] = np.where((arr[..., 3] == 0)[..., None], np.array(rgb), arr[..., :3])
        out = os.path.join(A, f'chest_real_{tag}_{side}.webp')
        Image.fromarray(arr, 'RGBA').save(out, 'WEBP', quality=92, alpha_quality=100, method=6)
        print(f'  chest_real_{tag}_{side}.webp {mw}x{mh} {os.path.getsize(out)/1e3:.0f} KB')


def punch(path, tag, quality=88):
    im = Image.open(path).convert('RGBA')
    W, H = im.size
    hole = Image.new('L', (W, H), 0)
    box_h = (CHEST_BOX[3] - CHEST_BOX[1]) * H
    for (cx, cy, rx, ry) in BUST_REAL[tag]:
        k = PL._hole_k(rx * W, ry * H, box_h)
        h = PL._hole_mask((W, H), cx * W, cy * H, rx * W, ry * H, k)
        hole = Image.fromarray(np.maximum(np.array(hole), np.array(h)))
    arr = np.array(im)
    arr[..., 3] = (arr[..., 3].astype(np.float32) * (1 - np.array(hole).astype(np.float32) / 255)).astype('uint8')
    Image.fromarray(arr, 'RGBA').save(path, 'WEBP', quality=quality, alpha_quality=100, method=6)
    print(f'  окно: {os.path.basename(path)} {W}x{H} {os.path.getsize(path)/1e6:.2f} MB')


def punch_hole(tag):
    punch(_master(tag), tag, 90)
    punch(_sm(tag), tag, 86)
    for mood in ('blink', 'shy'):
        p = os.path.join(A, f'art_real_emo_{tag}_{mood}.webp')
        if os.path.exists(p):
            punch(p, tag, 88)


if __name__ == '__main__':
    for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
        print(f'{tag}:')
        chest_patch(tag)   # прокола нет: маска ложится на целый арт
    print('готово')
