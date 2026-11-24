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
MASK = {                                # центр и радиусы эллипса в долях кадра спрайта
    'sg1': (0.525, 0.375, 0.085, 0.052),   # кофта, бюст под тканью
    'sg2': (0.520, 0.385, 0.090, 0.052),
    'sg3': (0.520, 0.360, 0.095, 0.055),   # топ, открытая грудь
    'sg4': (0.520, 0.370, 0.100, 0.058),   # откинулась, грудь крупнее в кадре
}


def shrink(src, dest, size):
    im = Image.open(src).convert('RGBA')
    im.resize(size, Image.LANCZOS).save(dest, 'WEBP', quality=86, alpha_quality=98, method=6)
    print(f'{os.path.basename(dest)} {size} {os.path.getsize(dest)/1e6:.2f} MB')


def punch_hole(tag):
    """Вырезаем в базовом кадре окно под грудью.

    Без этого патч, уезжая, оставляет под собой старые пиксели — виден
    гостинг (двойной контур). Окно меньше патча (82 % эллипса), поэтому
    край окна всегда закрыт непрозрачной серединой патча.
    """
    cx, cy, rx, ry = MASK[tag]
    for name in (f'art_day1_{tag}.webp', f'art_day1_{tag}_sm.webp'):
        path = os.path.join(A, name)
        im = Image.open(path).convert('RGBA')
        W, H = im.size
        m = Image.new('L', (W, H), 0)
        k = 0.58
        box = [int((cx-rx*k)*W), int((cy-ry*k)*H), int((cx+rx*k)*W), int((cy+ry*k)*H)]
        ImageDraw.Draw(m).ellipse(box, fill=255)
        m = m.filter(ImageFilter.GaussianBlur(max(2, int(min(rx*k*W, ry*k*H)*0.06))))
        arr = np.array(im)
        arr[..., 3] = (arr[..., 3].astype(np.float32) * (1 - np.array(m).astype(np.float32)/255)).astype('uint8')
        Image.fromarray(arr, 'RGBA').save(path, 'WEBP', quality=90 if 'sm' not in name else 86,
                                          alpha_quality=100, method=6)
        print(f'окно: {name} {W}x{H} {os.path.getsize(path)/1e6:.2f} MB')


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

    # жёсткое ядро + растушёвка только по внешнему кольцу:
    # иначе у края патч полупрозрачный и под ним просвечивает «окно»
    mask = Image.new('L', (mw, mh), 0)
    ImageDraw.Draw(mask).ellipse([mx-mrx, my-mry, mx+mrx, my+mry], fill=255)
    soft = mask.filter(ImageFilter.GaussianBlur(max(2, int(min(mrx, mry)*0.24))))
    core = Image.new('L', (mw, mh), 0)
    ImageDraw.Draw(core).ellipse([mx-mrx*0.70, my-mry*0.86, mx+mrx*0.70, my+mry*0.86], fill=255)
    mask = Image.fromarray(np.maximum(np.array(soft), np.array(core)))

    arr = np.array(crop)
    arr[..., 3] = (np.array(mask).astype(np.float32) * (arr[..., 3].astype(np.float32)/255)).astype('uint8')
    out = os.path.join(A, f'chest_{tag}.webp')
    Image.fromarray(arr, 'RGBA').save(out, 'WEBP', quality=92, alpha_quality=100, method=6)
    print(f'chest_{tag}.webp {CHEST_W}x{crop.height} {os.path.getsize(out)/1e3:.0f} KB')


if __name__ == '__main__':
    only_chest = '--chest' in sys.argv
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
