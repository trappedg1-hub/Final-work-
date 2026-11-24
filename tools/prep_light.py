# -*- coding: utf-8 -*-
"""Лёгкие версии кадров для телефона + маленький проп «грудь» с запечённой маской.

5K-мастера остаются в репозитории; в игру на телефоне отдаются _sm (srcset),
потому что 20-мегапиксельные текстуры + копия кадра под маску убивают FPS.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
A = os.path.join(ROOT, 'assets')

SM_SPRITE = (1170, 1560)     # 3:4
SM_ROOM = (1200, 1356)

CHEST_BOX = (0.22, 0.12, 0.78, 0.50)   # единый кроп для всех стадий (left, top, right, bottom)
CHEST_W = 720
MASK = {                                # центр и радиусы эллипса в долях кадра спрайта
    'sg1': (0.50, 0.30, 0.14, 0.070),
    'sg2': (0.50, 0.30, 0.14, 0.070),
    'sg3': (0.50, 0.27, 0.13, 0.065),
    'sg4': (0.50, 0.33, 0.15, 0.075),
}


def shrink(src, dest, size):
    im = Image.open(src).convert('RGBA')
    im.resize(size, Image.LANCZOS).save(dest, 'WEBP', quality=86, alpha_quality=98, method=6)
    print(f'{os.path.basename(dest)} {size} {os.path.getsize(dest)/1e6:.2f} MB')


def chest_patch(tag):
    im = Image.open(os.path.join(A, f'art_day1_{tag}.webp')).convert('RGBA')
    W, H = im.size
    x0, y0, x1, y1 = CHEST_BOX
    box = (int(W*x0), int(H*y0), int(W*x1), int(H*y1))
    crop = im.crop(box)
    cw, ch = crop.size
    k = CHEST_W / cw
    crop = crop.resize((CHEST_W, max(1, round(ch*k))), Image.LANCZOS)

    cx, cy, rx, ry = MASK[tag]
    mw, mh = CHEST_W, crop.height
    mx = (cx - x0) / (x1 - x0) * mw
    my = (cy - y0) / (y1 - y0) * mh
    mrx = rx / (x1 - x0) * mw
    mry = ry / (y1 - y0) * mh

    mask = Image.new('L', (mw, mh), 0)
    d = ImageDraw.Draw(mask)
    d.ellipse([mx-mrx, my-mry, mx+mrx, my+mry], fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(max(3, int(min(mrx, mry)*0.55))))
    mask = Image.fromarray(np.clip((np.array(mask).astype(np.float32)-6)/249*255, 0, 255).astype('uint8'))

    arr = np.array(crop)
    arr[..., 3] = (np.array(mask).astype(np.float32) * (arr[..., 3].astype(np.float32)/255)).astype('uint8')
    out = os.path.join(A, f'chest_{tag}.webp')
    Image.fromarray(arr, 'RGBA').save(out, 'WEBP', quality=92, alpha_quality=100, method=6)
    print(f'chest_{tag}.webp {CHEST_W}x{crop.height} {os.path.getsize(out)/1e3:.0f} KB')


if __name__ == '__main__':
    for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
        shrink(os.path.join(A, f'art_day1_{tag}.webp'), os.path.join(A, f'art_day1_{tag}_sm.webp'), SM_SPRITE)
        chest_patch(tag)
    for name in ('room_day1', 'room_fg'):
        shrink(os.path.join(A, f'{name}.webp'), os.path.join(A, f'{name}_sm.webp'), SM_ROOM)
