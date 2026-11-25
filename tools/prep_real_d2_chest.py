# -*- coding: utf-8 -*-
"""Пропы груди и окна физики для ВТОРОГО дня канона 2.

Геометрия снята по мелкой сетке на кадрах assets/real/art_real_day2_sgN_sm.webp.
У позы 2 второго дня грудь полностью закрыта коленями и руками — пропов нет
совсем, окно не пробивается и в игре слой физики для неё выключается.
У позы 3 фигура в профиль: видна только одна округлость (правая по экрану).

Порядок обязателен: chest_patch читает ещё целый _sm, punch_hole идёт после.
Повторный запуск на пробитых кадрах удвоит прокол — гонять только от чистых.

    python3 tools/prep_real_d2_chest.py
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

# (cx, cy, rx, ry) в долях кадра спрайта; None — округлость не видна
BUST_D2 = {
    'sg1': ((0.466, 0.304, 0.048, 0.040), (0.571, 0.297, 0.055, 0.042)),  # канон, нога на ногу
    'sg2': (None, None),                                                   # колени закрывают грудь
    'sg3': (None, (0.622, 0.334, 0.044, 0.046)),                           # профиль, видна одна
    'sg4': ((0.447, 0.300, 0.050, 0.042), (0.580, 0.298, 0.054, 0.044)),   # нога на подлокотнике
}


def _sm(tag):
    return os.path.join(A, f'art_real_day2_{tag}_sm.webp')


def _master(tag):
    return os.path.join(A, f'art_real_day2_{tag}.webp')


def chest_patch(tag):
    im = Image.open(_sm(tag)).convert('RGBA')
    W, H = im.size
    x0, y0, x1, y1 = CHEST_BOX
    crop = im.crop((int(W * x0), int(H * y0), int(W * x1), int(H * y1)))
    mw, mh = crop.size

    for side, geo in zip(SIDES, BUST_D2[tag]):
        if geo is None:
            print(f'  chest_real_day2_{tag}_{side}.webp — нет (округлость не видна)')
            continue
        cx, cy, rx, ry = geo
        mx = (cx - x0) / (x1 - x0) * mw
        my = (cy - y0) / (y1 - y0) * mh
        mrx = rx / (x1 - x0) * mw
        mry = ry / (y1 - y0) * mh
        mask = PL._bulge_mask((mw, mh), mx, my, mrx, mry)
        arr = np.array(crop)
        arr[..., 3] = (np.array(mask).astype(np.float32) * (arr[..., 3].astype(np.float32) / 255)).astype('uint8')
        rgb = Image.fromarray(arr[..., :3].astype('uint8')).filter(ImageFilter.GaussianBlur(9))
        arr[..., :3] = np.where((arr[..., 3] == 0)[..., None], np.array(rgb), arr[..., :3])
        out = os.path.join(A, f'chest_real_day2_{tag}_{side}.webp')
        Image.fromarray(arr, 'RGBA').save(out, 'WEBP', quality=92, alpha_quality=100, method=6)
        print(f'  chest_real_day2_{tag}_{side}.webp {mw}x{mh} {os.path.getsize(out)/1e3:.0f} KB')


def punch(path, tag, quality=88):
    im = Image.open(path).convert('RGBA')
    W, H = im.size
    hole = Image.new('L', (W, H), 0)
    box_h = (CHEST_BOX[3] - CHEST_BOX[1]) * H
    for geo in BUST_D2[tag]:
        if geo is None:
            continue
        cx, cy, rx, ry = geo
        k = PL._hole_k(rx * W, ry * H, box_h)
        h = PL._hole_mask((W, H), cx * W, cy * H, rx * W, ry * H, k)
        hole = Image.fromarray(np.maximum(np.array(hole), np.array(h)))
    if not hole.getbbox():
        print(f'  окно: {os.path.basename(path)} — не нужно')
        return
    arr = np.array(im)
    arr[..., 3] = (arr[..., 3].astype(np.float32) * (1 - np.array(hole).astype(np.float32) / 255)).astype('uint8')
    Image.fromarray(arr, 'RGBA').save(path, 'WEBP', quality=quality, alpha_quality=100, method=6)
    print(f'  окно: {os.path.basename(path)} {W}x{H} {os.path.getsize(path)/1e6:.2f} MB')


def punch_hole(tag):
    punch(_master(tag), tag, 90)
    punch(_sm(tag), tag, 86)
    for mood in ('blink', 'shy'):
        p = os.path.join(A, f'art_real_emo_day2_{tag}_{mood}.webp')
        if os.path.exists(p):
            punch(p, tag, 88)


if __name__ == '__main__':
    for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
        print(f'{tag}:')
        chest_patch(tag)   # прокола нет: маска ложится на целый арт
    print('готово')
