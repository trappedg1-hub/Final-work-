# -*- coding: utf-8 -*-
"""Пропы груди для ТРЕТЬЕГО дня канона 2 (йога в офисе).

Геометрия снята по сетке на кадрах assets/real/art_real_day3_sgN_sm.webp.
Все четыре позы сидят в кресле и грудь видна — пропы есть у всех.
Радиусы слева и справа выравниваются (иначе одна сторона меньше и читается
как «грудь не ровно»), центры остаются измеренными.

    python3 tools/prep_real_d3_chest.py
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
BUST_D3 = {
    'sg1': ((0.470, 0.330, 0.055, 0.045), (0.598, 0.320, 0.058, 0.045)),   # растяжка, сидит наискосок
    'sg2': ((0.245, 0.385, 0.056, 0.046), (0.375, 0.372, 0.056, 0.046)),   # откинулась, ноги на столе
    'sg3': ((0.455, 0.378, 0.054, 0.044), (0.578, 0.375, 0.054, 0.044)),   # «V» ногами, руки за головой
    'sg4': ((0.470, 0.352, 0.052, 0.043), (0.575, 0.348, 0.052, 0.043)),   # финал: нога поднята
}

# наклон корпуса по позе (град, как CHEST_TILT в index.html). Контейнер пропа
# в вёрстке повёрнут на этот угол, поэтому ОКНО в арте поворачиваем так же —
# иначе повёрнутый проп не совпадает с вырезом и в груди видны чёрные серпы.
TILT_D3 = {'sg1': -7, 'sg2': -10, 'sg3': -2, 'sg4': -3}


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


BUST_D3 = _sym(BUST_D3)


def _sm(tag):
    return os.path.join(A, f'art_real_day3_{tag}_sm.webp')


def _master(tag):
    return os.path.join(A, f'art_real_day3_{tag}.webp')


def chest_patch(tag):
    im = Image.open(_sm(tag)).convert('RGBA')
    W, H = im.size
    x0, y0, x1, y1 = CHEST_BOX
    crop = im.crop((int(W * x0), int(H * y0), int(W * x1), int(H * y1)))
    mw, mh = crop.size

    for side, geo in zip(SIDES, BUST_D3[tag]):
        if geo is None:
            print(f'  chest_real_day3_{tag}_{side}.webp — нет (округлость не видна)')
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
        arr = np.clip(_derotate(arr, tag, mw, mh, -TILT_D3.get(tag, 0)), 0, 255).astype('uint8')
        out = os.path.join(A, f'chest_real_day3_{tag}_{side}.webp')
        Image.fromarray(arr, 'RGBA').save(out, 'WEBP', quality=92, alpha_quality=100, method=6)
        print(f'  chest_real_day3_{tag}_{side}.webp {mw}x{mh} {os.path.getsize(out)/1e3:.0f} KB')


def punch(path, tag, quality=88):
    im = Image.open(path).convert('RGBA')
    W, H = im.size
    hole = Image.new('L', (W, H), 0)
    box_h = (CHEST_BOX[3] - CHEST_BOX[1]) * H
    for geo in BUST_D3[tag]:
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
        p = os.path.join(A, f'art_real_face_day3_{tag}_{mood}.webp')
        if os.path.exists(p):
            punch(p, tag, 88)




HOLE_SCALE = 0.62   # окно заметно меньше пропа: проп накрывает его на всём ходе пружины


def _hole_for(tag, size):
    """Окно под пропом (в пикселях кропа CHEST_BOX) — уменьшенная копия маски.

    Без окна арт под пропом остаётся статичным: кромка ткани внутри маски
    уезжает и рядом видна её вторая копия («двойная ткань»). Окно вырезает
    статичную копию, поэтому двигается ОДИН слой, и движение читается как
    настоящая деформация, а не как «поехавшее пятно».
    """
    import cv2
    mw, mh = size
    x0, y0, x1, y1 = CHEST_BOX
    out = np.zeros((mh, mw), dtype=np.float32)
    # точка вращения контейнера — как в chestSet(): центр между округлостями,
    # по Y — верх груди
    geos = [g for g in BUST_D3[tag] if g]
    mxm = (geos[0][0] + geos[1][0]) / 2
    mym = min(g[1] for g in geos) - max(g[3] for g in geos)
    cxc = (mxm - x0) / (x1 - x0) * mw
    cyc = (mym - y0) / (y1 - y0) * mh
    th = np.deg2rad(TILT_D3.get(tag, 0))
    R = np.array([[np.cos(th), -np.sin(th)], [np.sin(th), np.cos(th)]], dtype=np.float32)
    for side, geo in zip(SIDES, BUST_D3[tag]):
        if geo is None:
            continue
        cx, cy, rx, ry = geo
        mx = (cx - x0) / (x1 - x0) * mw
        my = (cy - y0) / (y1 - y0) * mh
        mrx = rx / (x1 - x0) * mw
        mry = ry / (y1 - y0) * mh
        crop = getattr(_hole_for, 'crop')
        m = np.array(PL._bulge_mask((mw, mh), mx, my, mrx, mry, crop), dtype=np.float32)
        # 1) ужимаем окно вокруг верха округлости (там же ось пружины)
        ox, oy = mx, my - mry * 0.92
        S = np.array([[HOLE_SCALE, 0, ox * (1 - HOLE_SCALE)],
                      [0, HOLE_SCALE, oy * (1 - HOLE_SCALE)]], dtype=np.float32)
        # 2) и поворачиваем вокруг точки контейнера — как повёрнут сам проп
        A = np.zeros((2, 3), dtype=np.float32)
        A[:, :2] = R
        A[:, 2] = R @ (-np.array([cxc, cyc], dtype=np.float32)) + np.array([cxc, cyc], dtype=np.float32)
        m = cv2.warpAffine(m, S, (mw, mh), flags=cv2.INTER_LINEAR)
        m = cv2.warpAffine(m, A, (mw, mh), flags=cv2.INTER_LINEAR)
        out = np.maximum(out, m / 255.0)
    out = np.clip(out * 255, 0, 255).astype('uint8')
    return Image.fromarray(out, 'L').filter(ImageFilter.GaussianBlur(5))


def punch(tag):
    """Окно в арте — НЕ используется.

    Отверстие в арте под пропом работает только если проп накрывает его на
    всём ходе пружины бит-в-бит; на повёрнутом контейнере (наклон корпуса)
    совпадение уезжает на десяток пикселей и сквозь щель видно фон — на груди
    появляются тёмные серпы. Поэтому двигаем проп над целым артом, а маска
    пропа гаснет раньше контура ткани (prep_light._bulge_mask).
    """
    from PIL import ImageChops  # noqa: F401
    for src, dest in ((_master(tag), 'master'), (_sm(tag), 'sm')):
        if not os.path.exists(src):
            continue
        im = Image.open(src).convert('RGBA')
        W, H = im.size
        x0, y0 = int(W * CHEST_BOX[0]), int(H * CHEST_BOX[1])
        x1, y1 = int(W * CHEST_BOX[2]), int(H * CHEST_BOX[3])
        _hole_for.crop = im.crop((x0, y0, x1, y1))
        hole = Image.new('L', (W, H), 0)
        hole.paste(_hole_for(tag, (x1 - x0, y1 - y0)), (x0, y0))
        arr = np.array(im)
        a = arr[..., 3].astype(np.float32)
        arr[..., 3] = np.clip(a * (1.0 - 0.97 * np.array(hole).astype(np.float32) / 255.0), 0, 255).astype('uint8')
        q = 90 if dest == 'master' else 86
        Image.fromarray(arr, 'RGBA').save(src, 'WEBP', quality=q, alpha_quality=100, method=6)
        print(f'  окно: {os.path.basename(src)} {W}x{H} {os.path.getsize(src)/1e6:.2f} MB')


def _container_xy(tag, mw, mh):
    """Точка вращения контейнера (как chestSet в index.html) в пикселях кропа."""
    x0, y0, x1, y1 = CHEST_BOX
    geos = [g for g in BUST_D3[tag] if g]
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


_FMT = os.path.join(A, 'chest_real_day3_{tag}_{side}.webp')

if __name__ == '__main__':
    for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
        print(f'{tag}:')
        chest_patch(tag)
        _level(_FMT, tag)   # окно (punch) не режем: см. комментарий в punch()
    print('готово')
