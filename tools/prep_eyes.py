# -*- coding: utf-8 -*-
"""Моргание и смущение из нарисованных кадров-вариантов.

Генерация «съезжает» на 1–2 % кадра, поэтому целое лицо накладывать нельзя —
двоится. Берём только участки, которые реально меняются (два глаза и, для
смущения, губы), каждый со своей мягкой маской, и запекаем в один маленький
RGBA-патч размером с лицо. Слой в игре — один div на эмоцию.
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'images', 'raw_day1')
A = os.path.join(ROOT, 'assets')

EYES = {
    'sg1': [(45.9, 16.2), (51.0, 14.0)],
    'sg2': [(45.4, 17.5), (50.5, 15.5)],
    'sg3': [(44.9, 17.8), (50.3, 15.6)],
    'sg4': [(43.9, 19.1), (50.4, 17.4)],
}
MOUTH = {'sg1': (51.4, 18.4), 'sg2': (51.0, 19.3), 'sg3': (50.9, 19.5), 'sg4': (50.8, 21.7)}
FACE_BOX = {   # левый верхний угол и размеры «области лица» в % кадра
    'sg1': (44.77, 10.80, 11.41, 9.38),
    'sg2': (45.20, 10.88, 11.50, 9.37),
    'sg3': (45.20, 10.96, 11.50, 9.37),
    'sg4': (44.31, 14.39, 13.28, 10.38),
}
EYE_HALF = (2.35, 1.85)
MOUTH_HALF = (2.7, 1.7)
OUT_W = {'sg1': 320, 'sg2': 320, 'sg3': 320, 'sg4': 400}
WITH_MOUTH = {'shy': True, 'blink': False}


def build(tag, mood, src_name):
    base = Image.open(os.path.join(RAW, f'_edit_{tag}.png')).convert('RGB')
    var = Image.open(os.path.join(RAW, src_name)).convert('RGB').resize(base.size, Image.LANCZOS)
    W, H = base.size
    l, t, bw, bh = FACE_BOX[tag]
    fbox = (int(W*l/100), int(H*t/100), int(W*(l+bw)/100), int(H*(t+bh)/100))

    layer = Image.new('RGBA', (fbox[2]-fbox[0], fbox[3]-fbox[1]), (0, 0, 0, 0))

    def paste(cx_pct, cy_pct, half, feather=0.75):
        hx = half[0]/100*W; hy = half[1]/100*H
        cx = cx_pct/100*W; cy = cy_pct/100*H
        # окно с запасом под растушёвку, но не задевая брови
        padx, pady = hx*0.55, hy*0.55
        box = (int(cx-hx-padx), int(cy-hy-pady), int(cx+hx+padx), int(cy+hy+pady))
        patch = var.crop(box)
        m = Image.new('L', patch.size, 0)
        d = ImageDraw.Draw(m)
        d.ellipse([padx, pady, patch.size[0]-padx, patch.size[1]-pady], fill=255)
        m = m.filter(ImageFilter.GaussianBlur(max(2, int(hx*feather*0.5))))
        layer.paste(patch, (box[0]-fbox[0], box[1]-fbox[1]), m)

    for eye in EYES[tag]:
        paste(eye[0], eye[1], EYE_HALF, 0.7)
    if WITH_MOUTH[mood]:
        paste(MOUTH[tag][0], MOUTH[tag][1], MOUTH_HALF, 0.8)

    w = OUT_W[tag]
    out_img = layer.resize((w, max(1, round(layer.height*w/layer.width))), Image.LANCZOS)
    out = os.path.join(A, f'face_{tag}_{mood}.webp')
    out_img.save(out, 'WEBP', quality=94, alpha_quality=100, method=6)
    print(f'face_{tag}_{mood}.webp {out_img.size} {os.path.getsize(out)/1e3:.0f} KB')


if __name__ == '__main__':
    for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
        build(tag, 'blink', f'_blink_{tag}.png')
        build(tag, 'shy', f'_face_{tag}.png')
