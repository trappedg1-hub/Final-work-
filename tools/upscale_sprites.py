# -*- coding: utf-8 -*-
"""
Day-1 art pipeline: border-flood chroma key -> soft alpha -> ACNet x4 -> 3:4 canvas -> WebP.

Key rules (v2, after the "erased eyes" incident):
  * ONLY the background connected to the image border is removed (PIL flood fill from
    many border seeds). Interior greens — emerald irises, shadows on the hoodie — are
    never touched, because they are not reachable from the edge.
  * soft alpha: the hard matte is blurred by FEATHER px, so the contour keeps a
    1.5 px antialiased rim instead of a stair-stepped cut.
  * despill: only inside a 3 px band along the new edge, g is clamped to max(r,b).
  * edge-fill: transparent pixels get the nearest figure colour before upscaling, so
    ACNet cannot smear the chroma green into the hair.

Usage:  python tools/upscale_sprites.py
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, 'images')
OUT = os.path.join(ROOT, 'assets')

CANVAS = (1560, 2080)      # 3:4 — head, face and body down to the knees stay in frame
TOP_PAD = 0.035            # breathing room above the head
FEATHER = 1.5              # px of alpha softening (master resolution)
FLOOD_THRESH = 120         # PIL colour-distance tolerance for the background fill

# stage -> raw green-screen source
JOBS = [
    ('sg1', 'f_s2.png'),
    ('sg2', 'f_s1.png'),
    ('sg3', 'sg3_sock_a.png'),
    ('sg4', 'day1_sg4_new_raw.png'),   # climax pose: legs forward, new approved art
]

# the screenshot plate is not perfectly uniform, so it needs a wider fill tolerance
FLOOD_OVERRIDE = {'sg4': 130}

MAGENTA = (255, 0, 255)


def bg_reference(im, inset=8, size=36):
    """Median of four corner patches — the true chroma colour, away from any UI chrome."""
    w, h = im.size
    patches = []
    for cx, cy in ((inset, inset), (w - inset - size, inset),
                   (inset, h - inset - size), (w - inset - size, h - inset - size)):
        patches.append(np.array(im.crop((cx, cy, cx + size, cy + size))).reshape(-1, 3))
    return np.median(np.concatenate(patches, 0), 0)


def key_green(im, thresh=FLOOD_THRESH, tight=85):
    """Chroma plate -> alpha, without ever touching the figure's interior greens.

    bg = (colour very close to the plate colour)  OR  (plate reachable from the border).
    Emerald irises sit ~170 colour-distance away from the plate, so neither test can
    reach them, while thin background slivers between arm and torso are removed by the
    colour test even when they are enclosed.
    """
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

    bg = colour_bg | border_bg
    alpha = np.where(bg, 0.0, 255.0)
    a_img = Image.fromarray(alpha.astype(np.uint8), 'L')

    # soft rim (1.5 px) — interior stays fully opaque
    soft = np.array(a_img.filter(ImageFilter.GaussianBlur(FEATHER))).astype(np.float32)
    soft = np.clip((soft - 12) / (255 - 24) * 255, 0, 255)

    # despill only in a band around the new edge
    edge_band = np.array(
        Image.fromarray((soft < 250).astype(np.uint8) * 255, 'L')
        .filter(ImageFilter.MaxFilter(11))
    ) > 127
    g, mx = src[..., 1], np.maximum(src[..., 0], src[..., 2])
    src[..., 1] = np.where(edge_band & (g > mx * 1.02), mx * 1.02, g)
    # semi-transparent rim: clamp the green channel completely so no halo survives
    rim = soft < 232
    src[..., 1] = np.where(rim & (g > mx), mx, src[..., 1])

    return Image.fromarray(np.dstack([np.clip(src, 0, 255), soft]).astype(np.uint8), 'RGBA'), ref


def fill_edges(rgb, alpha, iters=40):
    """Grow figure colours into the transparent area so upscaling cannot pull chroma in."""
    a = (alpha > 8).astype(np.float32)[..., None]
    img = rgb.astype(np.float32) * a
    known = (alpha > 8).astype(np.float32)
    for _ in range(iters):
        # 4-neighbour propagation of known colours, normalised by known weight
        p = np.pad(img, ((1, 1), (1, 1), (0, 0)), mode='edge')
        k = np.pad(known, ((1, 1), (1, 1)), mode='edge')
        acc = (p[:-2, 1:-1] + p[2:, 1:-1] + p[1:-1, :-2] + p[1:-1, 2:])
        wacc = (k[:-2, 1:-1] + k[2:, 1:-1] + k[1:-1, :-2] + k[1:-1, 2:])
        newly = (known < 0.5) & (wacc > 0.5)
        img[newly] = (acc[newly] / wacc[newly][:, None])
        known[newly] = 1.0
    return np.clip(img, 0, 255).astype(np.uint8)


def acnet_upscale(rgb_img, factor=4.0):
    from pyanime4k import upscale_images
    tmp_in = '/tmp/_rig_in.png'
    tmp_out = '/tmp/_rig_out.png'
    rgb_img.save(tmp_in)
    upscale_images([tmp_in], [tmp_out], factor=factor,
                   model_name='acnet-gan', processor_type='cpu')
    return Image.open(tmp_out).convert('RGB')


def normalise(img):
    """3:4 canvas, bottom aligned, centred — head and knees always inside the frame."""
    W, H = CANVAS
    k = (H * (1 - TOP_PAD)) / img.height
    w = max(1, round(img.width * k))
    im = img.resize((w, max(1, round(img.height * k))), Image.LANCZOS)
    canvas = Image.new('RGBA', (W, H), (0, 0, 0, 0))
    canvas.alpha_composite(im, ((W - im.width) // 2, H - im.height))
    return canvas


def run(tag, src_name, flood=90):
    src_path = os.path.join(IMG, src_name)
    im = Image.open(src_path).convert('RGB')
    w, h = im.size

    # the phone screenshot carries a small dark download button on the chroma plate
    if tag == 'sg4':
        plate = tuple(int(v) for v in bg_reference(im))
        arr = np.array(im)
        y0, y1 = int(h * 0.885), int(h * 0.995)
        x0, x1 = int(w * 0.33), int(w * 0.67)
        band = arr[y0:y1, x0:x1]
        dark = band.max(2) < 150
        band[dark] = plate
        arr[y0:y1, x0:x1] = band
        im = Image.fromarray(arr, 'RGB')

    keyed, ref = key_green(im, thresh=flood)
    arr = np.array(keyed)
    rgb, alpha = arr[..., :3], arr[..., 3]

    filled = fill_edges(rgb, alpha, iters=40)
    big = acnet_upscale(Image.fromarray(filled, 'RGB'), 4.0)
    a_up = Image.fromarray(alpha, 'L').resize(big.size, Image.LANCZOS)

    art = big.convert('RGBA')
    art.putalpha(a_up)
    art = normalise(art)

    dest = os.path.join(OUT, f'art_day1_{tag}.webp')
    art.save(dest, 'WEBP', quality=92, method=6)
    print(f'{tag}: {src_name} -> {CANVAS[0]}x{CANVAS[1]} '
          f'{os.path.getsize(dest) / 1e6:.2f} MB')


if __name__ == '__main__':
    for tag, src in JOBS:
        run(tag, src, FLOOD_OVERRIDE.get(tag, 90))
