# -*- coding: utf-8 -*-
"""Преп комнаты и стола-пропа: кей зелени у стола, ACNet x2, чистые webp."""
import os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prep_arts import key_chroma, fill_edges, acnet_upscale, MAGENTA

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'images', 'raw_room')
OUT = os.path.join(ROOT, 'assets')


def trim_alpha(im, pad=0):
    a = np.array(im)[..., 3]
    ys, xs = np.where(a > 8)
    if not len(ys):
        return im
    y0, y1 = max(0, ys.min() - pad), min(im.height, ys.max() + 1 + pad)
    x0, x1 = max(0, xs.min() - pad), min(im.width, xs.max() + 1 + pad)
    return im.crop((x0, y0, x1, y1))


def prep_desk(factor=2.0, out_w=2600):
    """Стол = столешница в перспективе от камеры, стоящей на её дальнем краю.

    Ключ: зелёный только там, где канал G доминирует, и только связный с рамкой
    (flood fill по маске) — светлая столешница с зелёным отливом не страдает.
    """
    im = Image.open(os.path.join(SRC, '_desk_v2.png')).convert('RGB')
    arr = np.array(im).astype(np.int16)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    is_green = (g > r + 40) & (g > b + 40)
    if is_green.mean() < 0.15:
        raise SystemExit('desk: зелени слишком мало — проверь исходник')

    # вся зелёная зона -> ровная пурпурная плашка, дальше обычный flood fill
    work = np.where(is_green[..., None], np.array(MAGENTA, np.int16), arr[..., :3]).astype(np.uint8)
    w_img = Image.fromarray(work, 'RGB')
    w, h = w_img.size
    for x in range(0, w, 16):
        for y in (0, h - 1):
            ImageDraw.floodfill(w_img, (x, y), (255, 255, 0), thresh=24)
    for y in range(0, h, 16):
        for x in (0, w - 1):
            ImageDraw.floodfill(w_img, (x, y), (255, 255, 0), thresh=24)
    filled_mask = np.array(w_img)
    bg = (filled_mask[..., 0] > 200) & (filled_mask[..., 1] > 200) & (filled_mask[..., 2] < 60)

    alpha = np.where(bg, 0.0, 255.0)
    a_img = Image.fromarray(alpha.astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(1.0))
    soft = np.clip((np.array(a_img).astype(np.float32) - 10) / 235 * 255, 0, 255)

    src = arr.astype(np.float32)
    edge = np.array(Image.fromarray((soft < 250).astype(np.uint8) * 255, 'L')
                    .filter(ImageFilter.MaxFilter(9))) > 127
    mx = np.maximum(src[..., 0], src[..., 2])
    src[..., 1] = np.where(edge & (src[..., 1] > mx), mx, src[..., 1])
    src[..., 2] = np.where(edge & (src[..., 2] > mx), mx, src[..., 2])
    src[..., 0] = np.clip(src[..., 0], 0, 255)

    base = Image.fromarray(np.dstack([np.clip(src, 0, 255), soft[..., None]]).astype(np.uint8), 'RGBA')
    arr2 = np.array(base)
    filled = fill_edges(arr2[..., :3], arr2[..., 3])
    big = acnet_upscale(Image.fromarray(filled, 'RGB'), factor)
    a_up = Image.fromarray(arr2[..., 3], 'L').resize(big.size, Image.LANCZOS)
    art = big.convert('RGBA'); art.putalpha(a_up)
    art = trim_alpha(art)
    print('desk trimmed', art.size)
    k = out_w / art.width
    art = art.resize((out_w, max(1, round(art.height * k))), Image.LANCZOS)
    dest = os.path.join(OUT, 'room_desk.webp')
    art.save(dest, 'WEBP', quality=92, alpha_quality=100, method=6)
    print(f'desk -> {art.size} {os.path.getsize(dest) / 1e6:.2f} MB ratio {art.height / art.width:.3f}')
    return art


def prep_plate(factor=4.0, crop_bottom=1227, edge_row=1018, ramp=20, q=88):
    """Плата комнаты: кроп низа -> ACNet x2 -> WebP. Передний план режется из того же
    массива, поэтому в игре BG и FG совпадают пиксель в пиксель."""
    src = Image.open(os.path.join(SRC, '_plate_a.png')).convert('RGB')
    plate = src.crop((0, 0, src.width, crop_bottom))
    big = acnet_upscale(plate, factor)
    # 5K: длинная сторона 5120
    if big.height != 5120:
        w5 = round(big.width * 5120 / big.height)
        big = big.resize((w5, 5120), Image.LANCZOS)
    k = big.height / crop_bottom
    edge = max(1, min(big.height - 1, int(round(edge_row * k))))

    dest = os.path.join(OUT, 'room_day1.webp')
    big.save(dest, 'WEBP', quality=q, method=6)
    print(f'room_day1 {big.size} {os.path.getsize(dest)/1e6:.2f} MB edge {edge/big.height*100:.1f}%')

    arr = np.array(big)
    a = np.full((big.height, big.width), 255, np.float32)
    top = max(0, edge - ramp)
    a[:top, :] = 0.0
    a[top:top + 2 * ramp, :] = np.linspace(0, 255, 2 * ramp, dtype=np.float32)[:, None]
    flat = arr.copy()
    flat[:top, :] = (24, 22, 30)
    out = np.dstack([flat, np.clip(a, 0, 255).astype(np.uint8)])
    fg = os.path.join(OUT, 'room_fg.webp')
    Image.fromarray(out, 'RGBA').save(fg, 'WEBP', quality=92, alpha_quality=100, method=6)
    print(f'room_fg {big.size} {os.path.getsize(fg)/1e6:.2f} MB alpha from {top/big.height*100:.1f}%')


if __name__ == '__main__':
    prep_plate()
