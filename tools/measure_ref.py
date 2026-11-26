# -*- coding: utf-8 -*-
"""Замеры кадра для сверки с каноном 2 (эталон B — поза «стоит у кресла»).

Считаем ровно те метрики, по которым канон описан в tools/canon2_style.md,
чтобы новый кадр можно было сравнить с эталоном числами, а не «на глаз».

Определения (все — по непрозрачным пикселям фигуры, фон отброшен):

* кадр приводится к ширине 520 px (как в описании канона);
* ``насыщенность`` — средняя S в HSV (0..1);
* ``яркость`` — средняя V в HSV (0..1);
* ``Lstd`` — разброс V по фигуре;
* ``p99`` — 99-й перцентиль V (есть ли настоящие белые блики);
* ``блики на коже`` — доля пикселей кожи с V > 0.935;
* ``контраст кожи`` — std V внутри кожи;
* ``края`` — доля пикселей с |Laplacian| > 0.10;
* ``жёсткие края`` — доля пикселей с |Laplacian| > 0.24;
* ``кожа RGB`` / ``волосы RGB`` — медианы по эвристическим маскам;
* ``высота фигуры`` — доля высоты кадра, занятая альфой.

Маска кожи: R > G > B, (R-B) в 18..95 уровней, V > 0.35.
Маска волос: светлый низконасыщенный тон (V > 0.45, S < 0.42, R >= G >= B),
взят только в верхней половине фигуры — там, где у героини волосы и шляпа.

    python3 tools/measure_ref.py assets/real/canon2_ref_stand_sm.webp
    python3 tools/measure_ref.py            # канон + дни 2/3 + эталон B
"""
import os
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, 'assets', 'real')
RAW = os.path.join(ROOT, 'images', 'raw_real')


def _stats(im):
    im = im.convert('RGBA')
    k = 520.0 / im.width
    im = im.resize((520, max(1, round(im.height * k))), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32)
    rgb, al = a[..., :3] / 255.0, a[..., 3] / 255.0
    sel = al > 0.78
    if not sel.any():
        raise RuntimeError('пустая альфа')
    mx, mn = rgb.max(2), rgb.min(2)
    v = mx
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    r, g, b = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    skin = sel & (r > g + 0.01) & (g > b) & ((r - b) > 0.07) & ((r - b) < 0.37) & (v > 0.35)
    hair = sel & (v > 0.45) & (s < 0.42) & (r >= g) & (g >= b)
    ys = np.nonzero(sel.any(1))[0]
    hair[: max(0, ys.min() + int((ys.max() - ys.min()) * 0.5))] = False

    gray = (rgb @ np.array([0.299, 0.587, 0.114], dtype=np.float32))
    lap = np.abs(np.gradient(np.gradient(gray, axis=0), axis=0) +
                 np.gradient(np.gradient(gray, axis=1), axis=1))
    lap = lap / 4.0

    out = {
        'насыщенность': s[sel].mean(),
        'яркость': v[sel].mean(),
        'Lstd': v[sel].std(),
        'p99': np.percentile(v[sel], 99),
        'блики на коже': (v[skin] > 0.935).mean() * 100 if skin.any() else 0.0,
        'контраст кожи': v[skin].std() if skin.any() else 0.0,
        'края': (lap[sel] > 0.10).mean() * 100,
        'жёсткие края': (lap[sel] > 0.24).mean() * 100,
        'кожа RGB': rgb[skin].mean(0) if skin.any() else np.zeros(3),
        'волосы RGB': rgb[hair].mean(0) if hair.any() else np.zeros(3),
        'высота фигуры': (ys.max() - ys.min() + 1) / float(np.asarray(im).shape[0]) * 100,
    }
    return out


def _fmt(name, st):
    sk = '/'.join(f'{x:.3f}' for x in st['кожа RGB'])
    hr = '/'.join(f'{x:.3f}' for x in st['волосы RGB'])
    return (f'{name:38s} sat {st["насыщенность"]:.3f}  V {st["яркость"]:.3f}  '
            f'Lstd {st["Lstd"]:.3f}  p99 {st["p99"]:.3f}  блики {st["блики на коже"]:.1f}%  '
            f'контраст {st["контраст кожи"]:.3f}  края {st["края"]:.4f}/{st["жёсткие края"]:.4f}  '
            f'кожа {sk}  волосы {hr}  h {st["высота фигуры"]:.1f}%')


def main(argv):
    if argv:
        files = argv
    else:
        files = [os.path.join(RAW, '_canon2_hero.png')]
        files += [os.path.join(A, f'art_real_day{d}_{t}_sm.webp') for d in ('2', '3') for t in ('sg1', 'sg2', 'sg3', 'sg4')]
        files += [os.path.join(A, 'canon2_ref_stand_sm.webp')]
    for p in files:
        if not os.path.exists(p):
            print(f'{os.path.basename(p):38s} — нет файла')
            continue
        print(_fmt(os.path.basename(p), _stats(Image.open(p))))


if __name__ == '__main__':
    main(sys.argv[1:])
