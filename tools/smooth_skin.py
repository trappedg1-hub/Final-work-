"""Снятие «песка» с кожи — один детерминированный проход.

Генератор иногда даёт на коже крапчатую текстуру («апельсиновая корка»).
Здесь она приглаживается медианой + лёгким гауссом, но только по маске кожи
и с мягким краем, поэтому складки, блики и контуры волос остаются на месте.

    python3 tools/smooth_skin.py IN.png --out OUT.png [--strength 0.7]
"""

import argparse
import numpy as np
from PIL import Image, ImageFilter


def skin_mask(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(2), a.min(2)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0.0)
    green = (g > 0.45) & (g > r * 1.20) & (g > b * 1.20)   # хромакей
    skin = (~green) & (mx > 0.42) & (s > 0.04) & (s < 0.42) & (r > b * 1.02)
    return skin.astype(np.float32)


def feather(mask, radius=5.0):
    m = Image.fromarray((mask * 255).astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(radius))
    return np.asarray(m).astype(np.float32) / 255.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('src')
    ap.add_argument('--out', required=True)
    ap.add_argument('--strength', type=float, default=0.7)
    args = ap.parse_args()

    im = Image.open(args.src).convert('RGB')
    a = np.asarray(im).astype(np.float32) / 255.0

    # медиана по «песку» + гаусс, чтобы не осталось ступенек
    med = im.filter(ImageFilter.MedianFilter(5)).filter(ImageFilter.GaussianBlur(1.1))
    soft = np.asarray(med).astype(np.float32) / 255.0

    m = feather(skin_mask(a))
    # сильнее там, где локальная дисперсия высокая (крап), слабее на градиентах
    lum = a.mean(2)
    var = np.abs(lum - np.asarray(Image.fromarray((lum * 255).astype(np.uint8), 'L')
                                   .filter(ImageFilter.GaussianBlur(3))).astype(np.float32) / 255.0)
    w = np.clip(args.strength * m, 0, 1) * np.clip(0.55 + var * 8.0, 0, 1)

    out = a * (1 - w[..., None]) + soft * w[..., None]
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(args.out)
    print(f'{args.out}: сглажено по коже, средний вес {w.mean():.3f}, макс {w.max():.3f}')


if __name__ == '__main__':
    main()
