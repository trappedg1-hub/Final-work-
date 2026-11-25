# -*- coding: utf-8 -*-
"""HD-сборка арта: ключ -> разворот свечения -> ACNet x4 (~5K) -> холст -> шарп.

Зачем: ACNet x2, за которым шёл апскейл холста вверх, размывал мелкие детали —
шнуровку корсета, вышивку, ресницы. Схема x2 -> x4: апскейлим с запасом и
уменьшаем в мастер, поэтому деталь остаётся резкой, а не растянутой.

Используется tools/prep_real_d4.py и tools/upscale_real_hd.py (дни 2-4).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_real as PR  # noqa: E402
import prep_arts as PA  # noqa: E402

FACTOR = 4.0               # ACNet x4 (~5K) -> даунсэмпл в мастер: держит детали
SHARP = dict(radius=1.6, percent=62, threshold=2)


def deglow(im):
    '''
    Свечение звезды — полупрозрачная лаванда поверх зелёного фона. Ключ такие
    пиксели не берёт (зелени в них много), и вокруг звезды оставался зелёный
    ореол. Разворачиваем смесь: знаем цвет фона BG, оцениваем долю фона по
    избытку зелени и восстанавливаем исходный цвет источника.

    d  = g - max(r,b)      — избыток зелени в пикселе
    a  = 1 - d / d(BG)     — доля источника (1 — чистое свечение, 0 — чистый фон)
    F  = (C - (1-a)*BG)/a  — цвет источника без подмешанного фона
    '''
    BG = np.array(PR.plate_colour(im), dtype=np.float32)
    d_bg = max(1.0, float(BG[1] - max(BG[0], BG[2])))

    keyed, _ref = PA.key_chroma(im)
    arr = np.array(keyed).astype(np.float32)
    rgb, al = arr[..., :3].copy(), arr[..., 3].copy()

    d = rgb[..., 1] - np.maximum(rgb[..., 0], rgb[..., 2])
    a = np.clip(1.0 - d / d_bg, 0.0, 1.0)
    # мягкий старт: слабую зелень (кожа, тени) не трогаем, только явную примесь
    weak = np.clip((d - 10.0) / 25.0, 0.0, 1.0)
    a = 1.0 - (1.0 - a) * weak

    hit = (weak > 0) & (al > 0)
    with np.errstate(divide='ignore', invalid='ignore'):
        F = (rgb - (1.0 - a[..., None]) * BG) / np.maximum(a[..., None], 1e-3)
    F = np.where(hit[..., None], np.clip(F, 0, 255), rgb)
    al = np.where(hit, al * a, al)

    # у нарисованного свечения есть жёсткая кайма (художник вёл полупрозрачной
    # кистью) — на зелёном она читалась как блик, после разворота даёт зубчатый
    # серый контур. Гасим внешнюю половину ореола, оставляя мягкое ядро.
    fade = np.clip((0.70 * d_bg - d) / (0.45 * d_bg), 0.0, 1.0)
    al = np.where(hit, al * fade, al)

    # на внешней границе свечения альфа падает рывком — получается зубчатый
    # «гребешок» вокруг звезды. Сглаживаем альфу только внутри зоны свечения.
    if hit.any():
        w = Image.fromarray((hit * 255).astype(np.uint8))
        w = w.filter(ImageFilter.MaxFilter(9)).filter(ImageFilter.GaussianBlur(2.5))
        am = np.asarray(w, dtype=np.float32) / 255.0
        al_s = np.asarray(Image.fromarray(al.astype(np.uint8))
                          .filter(ImageFilter.GaussianBlur(2.5)), dtype=np.float32)
        al = al * (1.0 - am) + al_s * am
    # совсем прозрачные места не оставляем с мусорным цветом — ACNet тянет его в край
    al = np.where(al < 6, 0, al)

    out = np.dstack([F, al]).clip(0, 255).astype(np.uint8)
    return Image.fromarray(out, 'RGBA')


def art_from(im, factor):
    '''deglow -> ключ/края/ACNet -> 3:4 холст (копия PR.to_alpha_art с шагом deglow).'''
    keyed = deglow(im)
    arr = np.array(keyed)
    rgb, alpha = arr[..., :3], arr[..., 3]
    filled = PA.fill_edges(rgb, alpha)
    big = PA.acnet_upscale(Image.fromarray(filled, 'RGB'), factor)
    a_up = Image.fromarray(alpha, 'L').resize(big.size, Image.LANCZOS)
    art = big.convert('RGBA')
    art.putalpha(a_up)
    PA.CANVAS, PA.TOP_PAD = PR.CANVAS, PR.TOP_PAD
    return PA.normalise(art)


def sharpen(art):
    '''
    USM только по RGB, альфа остаётся от ключа. Края силуэта не трогаем:
    там уже подложен despill, лишние ореолы вылезут на зелёном фоне.
    '''
    rgb = art.convert('RGB').filter(ImageFilter.UnsharpMask(**SHARP))
    out = rgb.convert('RGBA')
    out.putalpha(art.getchannel('A'))
    return out


