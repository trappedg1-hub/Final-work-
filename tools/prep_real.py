# -*- coding: utf-8 -*-
"""Пайплайн реалистичной версии (канон 2).

Отличие от дня 1: свой холст (2340x3120, 3:4), своя папка assets/real, и кадры
эмоций выравниваются по базе (генерация перерисовывает тело со сдвигом 5-8 px,
без выравнивания на монтаже дёргается всё тело).

Ключ, despill, заполнение краёв и ACNet — те же функции, что в prep_arts.py.

Usage:  python3 tools/prep_real.py [--factor 2]
"""
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_arts as PA  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'images', 'raw_real')
OUT = os.path.join(ROOT, 'assets', 'real')

CANVAS = (2340, 3120)     # 3:4 мастер (2x от _sm)
SM = (1170, 1560)
TOP_PAD = 0.02
PA.CANVAS_BACKUP = PA.CANVAS

POSES = ('sg1', 'sg2', 'sg3', 'sg4')
MOODS = ('blink', 'shy')


def grad(im, max_w=704):
    g = im.convert('L')
    if g.width > max_w:
        g = g.resize((max_w, round(g.height * max_w / g.width)), Image.LANCZOS)
    a = np.asarray(g, dtype=np.float32)
    return np.abs(np.diff(a, axis=1))[:-1, :] + np.abs(np.diff(a, axis=0))[:, :-1]


def best_shift(base, mov):
    A, B = grad(base), grad(mov)
    F, G = np.fft.rfft2(A), np.fft.rfft2(B)
    c = np.fft.irfft2(F * np.conj(G), s=A.shape)
    idx = np.unravel_index(np.argmax(c), c.shape)
    dy = idx[0] if idx[0] < A.shape[0] // 2 else idx[0] - A.shape[0]
    dx = idx[1] if idx[1] < A.shape[1] // 2 else idx[1] - A.shape[1]
    return int(dx), int(dy)


def plate_colour(im, inset=8, size=36):
    px = [np.array(im.crop((inset, inset, inset + size, inset + size))).reshape(-1, 3)]
    w, h = im.size
    px.append(np.array(im.crop((w - inset - size, h - inset - size, w - inset, h - inset))).reshape(-1, 3))
    return tuple(int(v) for v in np.median(np.concatenate(px, 0), 0))


def to_alpha_art(im):
    """Ключ -> альфа -> заполнение краёв -> ACNet x2 -> 3:4 холст."""
    keyed, _ref = PA.key_chroma(im)
    arr = np.array(keyed)
    rgb, alpha = arr[..., :3], arr[..., 3]
    filled = PA.fill_edges(rgb, alpha)
    big = PA.acnet_upscale(Image.fromarray(filled, 'RGB'), 2.0)
    a_up = Image.fromarray(alpha, 'L').resize(big.size, Image.LANCZOS)
    art = big.convert('RGBA')
    art.putalpha(a_up)
    PA.CANVAS, PA.TOP_PAD = CANVAS, TOP_PAD
    return PA.normalise(art)


def save(art, dest, master=True):
    if not master:
        art = art.resize(SM, Image.LANCZOS)
    art.save(dest, 'WEBP', quality=92, alpha_quality=100, method=6)
    print(f'  {os.path.basename(dest)} {art.size} {os.path.getsize(dest)/1e6:.2f} MB')


def main():
    os.makedirs(OUT, exist_ok=True)
    shifts = {}
    for tag in POSES:
        src = os.path.join(RAW, f'_g{tag[-1]}.png')
        print(f'{tag}:')
        art = to_alpha_art(Image.open(src).convert('RGB'))
        save(art, os.path.join(OUT, f'art_real_day1_{tag}.webp'), master=True)
        save(art, os.path.join(OUT, f'art_real_day1_{tag}_sm.webp'), master=False)

        base = Image.open(src).convert('RGB')
        for mood in MOODS:
            var = Image.open(os.path.join(RAW, f'_g_{mood}_{tag}.png')).convert('RGB')
            if var.size != base.size:
                var = var.resize(base.size, Image.LANCZOS)
            dx, dy = best_shift(base, var)
            shifts[f'{tag}_{mood}'] = [dx, dy]
            canvas = Image.new('RGB', var.size, plate_colour(var))
            canvas.paste(var, (dx, dy))
            emo = to_alpha_art(canvas)
            save(emo, os.path.join(OUT, f'art_real_emo_{tag}_{mood}.webp'), master=False)

    with open(os.path.join(OUT, 'align.json'), 'w') as fh:
        json.dump(shifts, fh, indent=1)
    print('сдвиги выравнивания:', shifts)


if __name__ == '__main__':
    main()
