# -*- coding: utf-8 -*-
"""Выравнивание кадров-эмоций по базовому кадру.

Генерация перерисовывает позу со сдвигом ~1-2 % кадра. Если просто
переключать кадры, на монтаже дёргается всё тело. Поэтому подбираем
масштаб+сдвиг по градиентам фигуры (FFT-кросс-корреляция) и печатаем
параметры — после этого кат виден только по глазам/улыбке.
"""
import os
import sys
import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'images', 'raw_day1')


def grad_mag(im, max_w=700):
    g = im.convert('L')
    if g.width > max_w:
        g = g.resize((max_w, max(1, round(g.height * max_w / g.width))), Image.LANCZOS)
    a = np.asarray(g, dtype=np.float32)
    gx = np.abs(np.diff(a, axis=1))[:-1, :]
    gy = np.abs(np.diff(a, axis=0))[:, :-1]
    m = gx + gy
    return (m - m.mean()) / (m.std() + 1e-6)


def best_shift(ref, mov):
    F = np.fft.rfft2(ref); G = np.fft.rfft2(mov)
    c = np.fft.irfft2(F * np.conj(G), s=ref.shape)
    idx = np.unravel_index(np.argmax(c), c.shape)
    dy = idx[0] if idx[0] < ref.shape[0] // 2 else idx[0] - ref.shape[0]
    dx = idx[1] if idx[1] < ref.shape[1] // 2 else idx[1] - ref.shape[1]
    return c.max() / ref.size, dx, dy


def search(base_path, var_path, scales=(1.0, 0.994, 0.997, 1.003, 1.006, 0.988, 0.982, 1.012, 1.018)):
    base = Image.open(base_path).convert('RGB')
    var0 = Image.open(var_path).convert('RGB').resize(base.size, Image.LANCZOS)
    ref = grad_mag(base)
    W, H = base.size
    sw = ref.shape[1] / W  # масштаб градиентной картинки

    best = None
    for s in scales:
        if s == 1.0:
            v = var0
        else:
            nw, nh = int(W * s), int(H * s)
            v = var0.resize((nw, nh), Image.LANCZOS)
            canvas = Image.new('RGB', (W, H), (0, 255, 0))
            canvas.paste(v, ((W - nw) // 2, (H - nh) // 2))
            v = canvas
        score, dx, dy = best_shift(ref, grad_mag(v))
        if best is None or score > best[0]:
            best = (score, s, dx, dy)
    score, s, dx, dy = best
    # назад в пиксели исходного кадра
    return dict(score=round(float(score), 3), scale=s,
                dx=int(round(dx / sw)), dy=int(round(dy / sw)))


if __name__ == '__main__':
    for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
        for mood, f in (('blink', f'_blink_{tag}.png'), ('shy', f'_face_{tag}.png')):
            p = os.path.join(RAW, f)
            if not os.path.exists(p):
                print(f'{tag} {mood}: нет файла'); continue
            print(tag, mood, search(os.path.join(RAW, f'_edit_{tag}.png'), p))
