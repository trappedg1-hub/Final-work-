# -*- coding: utf-8 -*-
"""
Prep кадров Day-1 (версия «она в кресле»): chroma key от границ -> мягкая альфа ->
despill -> заполнение краёв -> ACNet x2 -> холст 3:4 2340x3120 -> WebP q95.

Правила ключа (после инцидента с «вырезанными глазами»):
  * фон удаляется только если он связан с рамкой (flood fill от многих seeds)
    либо почти точно совпал с эталоном плашки (медиана угловых патчей);
  * изумрудные глаза сидят ~170 colour-distance от плашки — тесты до них не достают;
  * кромка 1.5 px, despill только в полосе у края;
  * цвет фигуры протягивается в прозрачную зону, чтобы апскейлер не тянул зелень.

Usage:  python tools/prep_arts.py [sg1 sg2 sg3 sg4]
"""
import os
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, 'images', 'raw_day1')
OUT_DIR = os.path.join(ROOT, 'assets')

CANVAS = (3840, 5120)      # 3:4 мастер 5K (19.7 МП)
TOP_PAD = 0.02
FEATHER = 1.5
FLOOD_THRESH = 110
TIGHT = 85
MAGENTA = (255, 0, 255)

JOBS = {
    'sg1': '_edit_sg1.png',
    'sg2': '_edit_sg2.png',
    'sg3': '_edit_sg3.png',
    'sg4': '_edit_sg4.png',
}


def bg_reference(im, inset=8, size=36):
    w, h = im.size
    patches = []
    for cx, cy in ((inset, inset), (w - inset - size, inset),
                   (inset, h - inset - size), (w - inset - size, h - inset - size)):
        patches.append(np.array(im.crop((cx, cy, cx + size, cy + size))).reshape(-1, 3))
    return np.median(np.concatenate(patches, 0), 0)


def key_chroma(im, thresh=FLOOD_THRESH, tight=TIGHT):
    rgb = im.convert('RGB')
    w, h = rgb.size
    src = np.array(rgb).astype(np.float32)
    ref = bg_reference(rgb)
    dist = np.abs(src - ref).sum(2)
    colour_bg = dist < tight

    work = rgb.copy()
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    seeds += [(x, 0) for x in range(0, w, 24)] + [(x, h - 1) for x in range(0, w, 24)]
    seeds += [(0, y) for y in range(0, h, 24)] + [(w - 1, y) for y in range(0, h, 24)]
    for s in seeds:
        try:
            ImageDraw.floodfill(work, s, MAGENTA, thresh=thresh)
        except Exception:
            pass
    fa = np.array(work)
    border_bg = (fa[..., 0] > 245) & (fa[..., 1] < 12) & (fa[..., 2] > 245)

    # страховка от «дыр»: фоном может быть только пиксель, где зелёный доминирует.
    # без этого тёмное кресло и чёрные шорты попадали в допуск суммы и выедались.
    green_dom = (src[..., 1] > src[..., 0] + 28) & (src[..., 1] > src[..., 2] + 28)
    bg = (colour_bg | border_bg) & green_dom
    alpha = np.where(bg, 0.0, 255.0)
    a_img = Image.fromarray(alpha.astype(np.uint8), 'L')
    soft = np.array(a_img.filter(ImageFilter.GaussianBlur(FEATHER))).astype(np.float32)
    soft = np.clip((soft - 12) / (255 - 24) * 255, 0, 255)

    edge_band = np.array(
        Image.fromarray((soft < 250).astype(np.uint8) * 255, 'L').filter(ImageFilter.MaxFilter(11))
    ) > 127
    g, mx = src[..., 1], np.maximum(src[..., 0], src[..., 2])
    src[..., 1] = np.where(edge_band & (g > mx * 1.02), mx * 1.02, g)
    rim = soft < 232
    src[..., 1] = np.where(rim & (g > mx), mx, src[..., 1])

    return Image.fromarray(np.dstack([np.clip(src, 0, 255), soft]).astype(np.uint8), 'RGBA'), ref


def fill_edges(rgb, alpha, iters=48):
    a = (alpha > 8).astype(np.float32)[..., None]
    img = rgb.astype(np.float32) * a
    known = (alpha > 8).astype(np.float32)
    for _ in range(iters):
        p = np.pad(img, ((1, 1), (1, 1), (0, 0)), mode='edge')
        k = np.pad(known, ((1, 1), (1, 1)), mode='edge')
        acc = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:])
        wacc = (k[:-2, 1:-1] + k[2:, 1:-1] + k[1:-1, :-2] + k[1:-1, 2:])
        newly = (known < 0.5) & (wacc > 0.5)
        img[newly] = (acc[newly] / wacc[newly][:, None])
        known[newly] = 1.0
    return np.clip(img, 0, 255).astype(np.uint8)


def acnet_upscale(rgb_img, factor=2.0):
    from pyanime4k import upscale_images
    tmp_in, tmp_out = '/tmp/_art_in.png', '/tmp/_art_out.png'
    rgb_img.save(tmp_in)
    upscale_images([tmp_in], [tmp_out], factor=factor,
                   model_name='acnet-gan', processor_type='cpu')
    return Image.open(tmp_out).convert('RGB')


def normalise(img):
    W, H = CANVAS
    k = (H * (1 - TOP_PAD)) / img.height
    w, h = max(1, round(img.width * k)), max(1, round(img.height * k))
    im = img.resize((w, h), Image.LANCZOS)
    if w > W:
        left = (w - W) // 2
        im = im.crop((left, 0, left + W, h))
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((W - im.width) // 2, H - im.height))
    return canvas


def run(tag, src_name, factor=4.0):
    im = Image.open(os.path.join(SRC_DIR, src_name)).convert('RGB')
    keyed, ref = key_chroma(im)
    arr = np.array(keyed)
    rgb, alpha = arr[..., :3], arr[..., 3]

    filled = fill_edges(rgb, alpha)
    big = acnet_upscale(Image.fromarray(filled, 'RGB'), factor)
    a_up = Image.fromarray(alpha, 'L').resize(big.size, Image.LANCZOS)

    art = big.convert('RGBA')
    art.putalpha(a_up)
    art = normalise(art)

    dest = os.path.join(OUT_DIR, f'art_day1_{tag}.webp')
    art.save(dest, 'WEBP', quality=90, alpha_quality=100, method=6)
    print(f'{tag}: {os.path.basename(src_name)} plate rgb({",".join(str(int(v)) for v in ref)}) '
          f'-> {CANVAS[0]}x{CANVAS[1]} {os.path.getsize(dest) / 1e6:.2f} MB')


if __name__ == '__main__':
    tags = sys.argv[1:] or list(JOBS)
    for t in tags:
        run(t, JOBS[t])
