# -*- coding: utf-8 -*-
"""Пропы груди для ЧЕТВЁРТОГО дня канона 2 (волшебница).

Геометрия снята по сетке на кадрах assets/real/art_real_day4_sgN_sm.webp.
Грудь здесь в жёстком корсете: пропы двигают только открытую кожу над верхней
кромкой (двигать вышивку корсета нельзя — читается как поролон). В позе 2
грудь закрыта руками и палочкой — пропов нет, как у дня 2.
Радиусы слева и справа выравниваются (иначе одна сторона меньше и читается
как «грудь не ровно»), центры остаются измеренными.

    python3 tools/prep_real_d4_chest.py
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
# Маски шире прежних: проп обязан накрывать ВСЮ округлость вместе с низом
# (иначе двигался «пятачок» и физика читалась вялой). Растушёвка при этом
# гаснет до контура ткани — гейт по краям в prep_light это держит.
BUST_D4 = {
    'sg1': ((0.440, 0.318, 0.052, 0.030), (0.494, 0.314, 0.052, 0.030)),   # сидит, палочка у лица
    'sg2': ((0.469, 0.320, 0.050, 0.029), (0.525, 0.318, 0.050, 0.029)),   # свернулась, звезда у ключиц
    'sg3': ((0.468, 0.325, 0.048, 0.029), (0.537, 0.322, 0.048, 0.029)),   # рука за шеей, палочка вверх
    'sg4': ((0.472, 0.307, 0.048, 0.029), (0.549, 0.304, 0.048, 0.029)),   # откинулась, палочка за головой
}

# наклон корпуса по позе (град, как CHEST_TILT в index.html). Контейнер пропа
# в вёрстке повёрнут на этот угол, поэтому ОКНО в арте поворачиваем так же —
# иначе повёрнутый проп не совпадает с вырезом и в груди видны чёрные серпы.
TILT_D4 = {'sg1': 0, 'sg2': 0, 'sg3': 0, 'sg4': 0}


def _sym(tbl):
    """Радиусы слева и справа выравниваем: иначе одна сторона заметно меньше
    и грудь читается как «не ровно». Центры остаются как измерены."""
    out = {}
    for tag, v in tbl.items():
        v = list(v)
        if len(v) == 2 and v[0] and v[1]:
            rx = (v[0][2] + v[1][2]) / 2.0
            ry = (v[0][3] + v[1][3]) / 2.0
            v[0] = tuple(v[0][:2]) + (rx, ry)
            v[1] = tuple(v[1][:2]) + (rx, ry)
        out[tag] = tuple(v)
    return out


BUST_D4 = _sym(BUST_D4)


def _sm(tag):
    return os.path.join(A, f'art_real_day4_{tag}_sm.webp')


def _master(tag):
    return os.path.join(A, f'art_real_day4_{tag}.webp')


def chest_patch(tag):
    im = Image.open(_sm(tag)).convert('RGBA')
    W, H = im.size
    x0, y0, x1, y1 = CHEST_BOX
    crop = im.crop((int(W * x0), int(H * y0), int(W * x1), int(H * y1)))
    mw, mh = crop.size

    for side, geo in zip(SIDES, BUST_D4[tag]):
        if geo is None:
            print(f'  chest_real_day4_{tag}_{side}.webp — нет (округлость не видна)')
            continue
        cx, cy, rx, ry = geo
        mx = (cx - x0) / (x1 - x0) * mw
        my = (cy - y0) / (y1 - y0) * mh
        mrx = rx / (x1 - x0) * mw
        mry = ry / (y1 - y0) * mh
        mask = PL._bulge_mask((mw, mh), mx, my, mrx, mry, crop)
        arr = np.array(crop)
        arr[..., 3] = (np.array(mask).astype(np.float32) * (arr[..., 3].astype(np.float32) / 255)).astype('uint8')
        rgb = Image.fromarray(arr[..., :3].astype('uint8')).filter(ImageFilter.GaussianBlur(9))
        arr[..., :3] = np.where((arr[..., 3] == 0)[..., None], np.array(rgb), arr[..., :3])
        # Контейнер пропа в вёрстке повёрнут на наклон корпуса (CHEST_TILT).
        # Содержимое пропа поэтому пре-поворачиваем на ОБРАТНЫЙ угол вокруг той
        # же точки: в покое поворот компенсируется и проп лежит ровно на арте,
        # а пружина деформирует грудь вдоль тела, а не по вертикали кадра.
        arr = np.clip(_derotate(arr, tag, mw, mh, -TILT_D4.get(tag, 0)), 0, 255).astype('uint8')
        out = os.path.join(A, f'chest_real_day4_{tag}_{side}.webp')
        Image.fromarray(arr, 'RGBA').save(out, 'WEBP', quality=92, alpha_quality=100, method=6)
        print(f'  chest_real_day4_{tag}_{side}.webp {mw}x{mh} {os.path.getsize(out)/1e3:.0f} KB')


def punch(path, tag, quality=88):
    im = Image.open(path).convert('RGBA')
    W, H = im.size
    hole = Image.new('L', (W, H), 0)
    box_h = (CHEST_BOX[3] - CHEST_BOX[1]) * H
    for geo in BUST_D4[tag]:
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


def _container_xy(tag, mw, mh):
    """Точка вращения контейнера (как chestSet в index.html) в пикселях кропа."""
    x0, y0, x1, y1 = CHEST_BOX
    geos = [g for g in BUST_D4[tag] if g]
    mxm = (geos[0][0] + geos[1][0]) / 2
    mym = min(g[1] for g in geos) - max(g[3] for g in geos)
    return (mxm - x0) / (x1 - x0) * mw, (mym - y0) / (y1 - y0) * mh


def _derotate(arr, tag, mw, mh, deg):
    """Поворот содержимого пропа вокруг точки контейнера (cv2, бикубика)."""
    import cv2
    if abs(deg) < 1e-6:
        return arr
    th = np.deg2rad(deg)
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]], dtype=np.float32)
    cx, cy = _container_xy(tag, mw, mh)
    A = np.zeros((2, 3), dtype=np.float32)
    A[:, :2] = R
    A[:, 2] = R @ (-np.array([cx, cy], dtype=np.float32)) + np.array([cx, cy], dtype=np.float32)
    return cv2.warpAffine(arr.astype(np.float32), A, (mw, mh), flags=cv2.INTER_LANCZOS4,
                          borderValue=(0, 0, 0, 0))


def _level(fmt, tag):
    """Выравниваем «массу» масок левой и правой груди: перекос читается как
    «не ровно»."""
    items = []
    for side in SIDES:
        p = fmt.format(tag=tag, side=side)
        if os.path.exists(p):
            items.append((p, np.array(Image.open(p).convert('RGBA'))))
    if len(items) < 2:
        return
    mass = [im[..., 3].astype(np.float32).sum() for _, im in items]
    tgt = max(mass)
    for (p, im), m in zip(items, mass):
        k = min(1.22, tgt / max(m, 1.0))
        if abs(k - 1.0) < 0.03:
            continue
        a = im.copy()
        a[..., 3] = np.clip(a[..., 3].astype(np.float32) * k, 0, 255).astype('uint8')
        Image.fromarray(a, 'RGBA').save(p, 'WEBP', quality=92, alpha_quality=100, method=6)
        print(f'  выровнено {os.path.basename(p)} x{k:.2f}')


_FMT = os.path.join(A, 'chest_real_day4_{tag}_{side}.webp')

if __name__ == '__main__':
    for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
        print(f'{tag}:')
        chest_patch(tag)
        _level(_FMT, tag)   # окно (punch) не режем: см. комментарий в punch()
    print('готово')
