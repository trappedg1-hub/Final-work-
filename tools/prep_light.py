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
    'sg1': ((0.494, 0.359, 0.030, 0.034), (0.589, 0.343, 0.066, 0.041)),  # кофта: правая видна целиком, левая за рукой
    'sg2': ((0.451, 0.354, 0.060, 0.054), (0.579, 0.348, 0.066, 0.051)),
    'sg3': ((0.442, 0.345, 0.063, 0.045), (0.586, 0.340, 0.065, 0.047)),  # топ
    'sg4': ((0.426, 0.430, 0.072, 0.038), (0.596, 0.424, 0.070, 0.040)),  # откинулась: цепляем полотно ПОД кромкой майки
}
SIDES = ('l', 'r')
CORE_K = 0.52    # непрозрачное ядро (доля контура груди)
HULL_K = 0.66    # внешняя граница растушёвки — НЕ доходит до контура
JIGGLE = 0.021   # пик пружины в долях высоты кропа (как в CSS)
HOLE_PAD = 0.06  # запас окна на растушёвку


def shrink(src, dest, size):
    im = Image.open(src).convert('RGBA')
    im.resize(size, Image.LANCZOS).save(dest, 'WEBP', quality=86, alpha_quality=98, method=6)
    print(f'{os.path.basename(dest)} {size} {os.path.getsize(dest)/1e6:.2f} MB')


def _ellipse_mask(size, cx, cy, rx, ry, k):
    m = Image.new('L', size, 0)
    ImageDraw.Draw(m).ellipse([cx - rx*k, cy - ry*k, cx + rx*k, cy + ry*k], fill=255)
    return m


def _bust_mask(size, cx, cy, rx, ry):
    """Ядро + мягкая растушёвка наружу, целиком ВНУТРИ нарисованного контура.

    Растушёвка обязана погаснуть раньше, чем дойдёт до контура: иначе при
    движении рядом с неподвижным нарисованным контуром появляется его
    полупрозрачная копия — тот самый двойной контур (гостинг).
    """
    hull = _ellipse_mask(size, cx, cy, rx, ry, HULL_K)
    hull = hull.filter(ImageFilter.GaussianBlur(max(2, int(min(rx, ry) * 0.075))))
    core = _ellipse_mask(size, cx, cy, rx, ry, CORE_K)
    return Image.fromarray(np.maximum(np.array(hull), np.array(core)))


def _bulge_mask(size, cx, cy, rx, ry, img=None):
    """Маска груди для физики: ядро по округлости + широкая растушёвка наружу.

    Прокола в кадре больше нет, поэтому маска может быть свободнее: она ложится
    поверх целого арта, а на краю плавно гаснет. Движение выходит «кругом
    груди», а не пятном, и не рвёт одежду — маска тянет кожу и ткань вместе.
    """
    # ядро — только сама округлость, растушёвка гаснет ДО контура груди:
    # иначе маска заезжает на рукав и тянет ткань, которой двигаться незачем
    core = _ellipse_mask(size, cx, cy, rx, ry, 0.54)
    soft = _ellipse_mask(size, cx, cy, rx, ry, 0.80)
    soft = soft.filter(ImageFilter.GaussianBlur(max(2, int(min(rx, ry) * 0.10))))
    core_a = np.array(core).astype(np.float32) / 255.0
    soft_a = np.array(soft).astype(np.float32) / 255.0
    m = np.maximum(core_a, soft_a)

    if img is not None:
        # маска гаснет там, где в кадре проходит контур: кромка одежды, рукав,
        # шов. Иначе эти пиксели уезжают вместе с грудью и край ткани «дышит»
        g = np.asarray(img.convert('L').filter(ImageFilter.GaussianBlur(1.2)), dtype=np.float32)
        gx = np.zeros_like(g); gy = np.zeros_like(g)
        gx[:, 1:-1] = g[:, 2:] - g[:, :-2]
        gy[1:-1, :] = g[2:, :] - g[:-2, :]
        mag = np.hypot(gx, gy)
        edge = (mag > 26).astype(np.float32) * 255.0
        edge = np.asarray(Image.fromarray(edge.astype('uint8'), 'L')
                          .filter(ImageFilter.MaxFilter(7))
                          .filter(ImageFilter.GaussianBlur(6)), dtype=np.float32) / 255.0
        # гасим у контуров только растушёвку; ядро внутри груди остаётся целым,
        # иначе внутренние складки ткани съедают всю маску и движение пропадает
        m = np.maximum(core_a * 0.92, soft_a * (1.0 - 0.92 * edge))

        # и не трогаем то, что грудью не является: зелёный фон и тёмный стул.
        # Иначе на краю маски уезжает спинка кресла — «грудь цепляет стул».
        arr = np.asarray(img.convert('RGB')).astype(np.float32)
        green = np.linalg.norm(arr - np.array([13.0, 178.0, 38.0])[None, None, :], axis=2) < 62
        # Стул — это почти чёрный и обесцвеченный; тень на ткани теплее и
        # светлее (p5 ≈ 85), поэтому порог низкий: иначе тень съедала маску
        # с одной стороны и грудь выглядела «не ровно».
        sat = arr.max(axis=2) - arr.min(axis=2)
        dark = (arr.mean(axis=2) < 62) & (sat < 34)
        keep = (~(green | dark)).astype(np.float32)
        keep = np.asarray(Image.fromarray((keep * 255).astype('uint8'), 'L')
                          .filter(ImageFilter.GaussianBlur(4)), dtype=np.float32) / 255.0
        keep_hard = (~(green | dark)).astype(np.float32)  # без размытия: стул не трогаем вообще
        m = m * keep * keep_hard
    return Image.fromarray((np.clip(m, 0, 1) * 255).astype('uint8'), 'L')


def _hole_k(rx, ry, box_h):
    """Радиус окна так, чтобы проп на всём ходе пружины оставался над ним.

    Ядро уезжает вниз на JIGGLE * высоту кропа. Чтобы сверху не открылось
    прозрачное «окно» (сквозь него видно фон), окно должно быть меньше
    ядра ровно на этот ход плюс запас на растушёвку.
    """
    dy = JIGGLE * box_h
    k = CORE_K - dy / max(1e-6, min(rx, ry)) - HOLE_PAD
    return max(0.26, min(CORE_K - 0.05, k))


def _hole_mask(size, cx, cy, rx, ry, k):
    m = _ellipse_mask(size, cx, cy, rx, ry, k)
    return m.filter(ImageFilter.GaussianBlur(max(2, int(min(rx, ry) * 0.05))))


def _punch(path, tag, quality=90):
    im = Image.open(path).convert('RGBA')
    W, H = im.size
    hole = Image.new('L', (W, H), 0)
    box_h = (CHEST_BOX[3] - CHEST_BOX[1]) * H
    for (cx, cy, rx, ry) in BUST[tag]:
        k = _hole_k(rx * W, ry * H, box_h)
        h = _hole_mask((W, H), cx * W, cy * H, rx * W, ry * H, k)
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
    """Два маленьких пропа: левая и правая грудь (общий кроп, разная альфа).

    Кроп берём из той же версии кадра, что видит телефон (`_sm`, 1170), и БЕЗ
    масштабирования: тогда пиксели пропа совпадают с базой один в один и по
    кромке маски не проступает овал.
    """
    im = Image.open(os.path.join(A, f'art_day1_{tag}_sm.webp')).convert('RGBA')
    W, H = im.size
    x0, y0, x1, y1 = CHEST_BOX
    box = (int(W*x0), int(H*y0), int(W*x1), int(H*y1))
    crop = im.crop(box)
    mw, mh = crop.size

    for side, (cx, cy, rx, ry) in zip(SIDES, BUST[tag]):
        mx = (cx - x0) / (x1 - x0) * mw
        my = (cy - y0) / (y1 - y0) * mh
        mrx = rx / (x1 - x0) * mw
        mry = ry / (y1 - y0) * mh
        mask = _bust_mask((mw, mh), mx, my, mrx, mry)
        arr = np.array(crop)
        arr[..., 3] = (np.array(mask).astype(np.float32) * (arr[..., 3].astype(np.float32)/255)).astype('uint8')
        # заливка цвета под прозрачность: иначе при уменьшении пропа (телефон,
        # 720 -> ~540 px) край растушёвки темнеет и по контуру маски видна кайма
        rgb = Image.fromarray(arr[..., :3].astype('uint8')).filter(ImageFilter.GaussianBlur(9))
        arr[..., :3] = np.where((arr[..., 3] == 0)[..., None], np.array(rgb), arr[..., :3])
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
