# -*- coding: utf-8 -*-
"""HD-сборка арта ПЯТОГО дня (пляжный стрим) из сырых генераций.

Кадры дня 5 рисуются на ровном тёмном студийном фоне, а не на хроме, поэтому
ключа здесь нет: апскейл идёт по RGB, альфа появится на шаге locked-кадров
(финальные позы генерируются на плоском зелёном, как день 4).

Пайплайн тот же, что у эталона B:
    сырой PNG -> ACNet x4 -> USM (HD.sharpen) -> grade() в LAB
    -> 3:4 холст 2340x3120 (тёмная подложка) -> WebP q92

    python3 tools/prep_real_d5.py p1 p2        # только выбранные кадры
    python3 tools/prep_real_d5.py              # все из JOBS
    python3 tools/prep_real_d5.py --factor 2 p3
"""
import os
import sys

import numpy as np
from PIL import Image, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_arts as PA  # noqa: E402
import prep_hd as HD  # noqa: E402
import prep_real as PR  # noqa: E402
import match_style as MS  # noqa: E402

RAW = PR.RAW
OUT = os.path.join(RAW, 'hd_d5')
REF_KEYED = os.path.join(PR.ROOT, 'tools', 'refs', 'canon2_ref_stand_sm.webp')

# тег -> сырой файл (тестовые проходы дня 5 в каноне 2)
JOBS = {
    # основной тестовый проход дня 5 (каталожный регистр, канон 2)
    'p1': '_d5P2_p1.png',      # стойка у кресла, топ-бант + шорты
    'p2': '_d5P2_p2.png',      # сидит на краю кресла, топ распахнут
    'p3': '_d5P2_p3.png',      # лежит на боку, только бикини
    'p4': '_d5P2_p4.png',      # финал: стойка у кресла, только бикини
    # проход «Y»: новые ракурсы с креслом и на полу
    **{f'y{i}': f'_d5Y1_p{i}.png' for i in (1, 2, 3, 4, 5, 6)},
    # проход «X»: кресло + пол, ещё горячее
    **{f'x{i}': f'_d5X1_p{i}.png' for i in (2, 3, 4, 5, 7, 8, 9, 10)},
    # проход «chair tease»: кресло как элемент фан-сервиса
    'w1': '_d5W1_p1.png',
    'w2': '_d5W1_p2.png',
    'w3': '_d5W1_p3.png',
    'w4': '_d5W1_p4.png',
    'w5': '_d5W1_p5.png',
    # проход «tease v»: бантики на белье, ракурсы со спины, playful
    'v1': '_d5V1_p1.png',
    'v2': '_d5V1_p2.png',
    'v3': '_d5V1_p3.png',
    'v4': '_d5V1_p4.png',
    'v5': '_d5V1_p5.png',
    # проход «tease»: ракурсы со спины, попочка, только бикини в 3-5
    'u1': '_d5U1_p1.png',
    'u2': '_d5U1_p2.png',
    'u3': '_d5U1_p3.png',
    'u4': '_d5U1_p4.png',
    'u5': '_d5U1_p5.png',
    # полный проход дня 5 в каноническом STYLE LOCK, костюм переделан
    't1': '_d5T1_p1.png',
    't2': '_d5T1_p2.png',
    't3': '_d5T1_p3.png',
    't4': '_d5T1_p4.png',
    # новый проход с каноническим STYLE LOCK (глянец, контраст внутри кожи)
    'r1': '_d5R1_p1.png',
    'r4': '_d5R1_p4.png',
    # прошлые проходы — для сравнения
    'o1': '_d5P1_p1.png',
    'o2': '_d5N1_p2.png',
    'o3': '_d5P1_p3.png',
    'o4': '_d5N1_p4.png',
}


def backplate(im, size=48):
    """Цвет фона — медиана четырёх углов кадра."""
    w, h = im.size
    patches = [im.crop(box) for box in ((0, 0, size, size), (w - size, 0, w, size),
                                        (0, h - size, size, h), (w - size, h - size, w, h))]
    px = np.concatenate([np.asarray(p).reshape(-1, 3) for p in patches], 0)
    return tuple(int(v) for v in np.median(px, 0))


def figure_mask(im, bg, tol=12):
    """Грубая маска фигуры по отличию от цвета фона.

    Нужна только для замера тона: `grade()` берёт перцентили по непрозрачным
    пикселям, и если считать их по всему кадру, тёмный фон подставки тянет
    q50 вниз и кривая выбеливает всю картинку (проверено на первом проходе).
    Ключом эта маска не является — альфа у кадра остаётся полной.
    """
    arr = np.asarray(im, dtype=np.float32)
    diff = np.abs(arr - np.array(bg, dtype=np.float32)).max(axis=2)
    mask = (diff > tol).astype(np.uint8) * 255
    m = Image.fromarray(mask, 'L')
    m = m.filter(ImageFilter.MaxFilter(5)).filter(ImageFilter.MinFilter(5))
    m = m.filter(ImageFilter.GaussianBlur(1.5))
    return m


def canon_match(rgb, weight=1.0, fig=None):
    """Доводка под канон 2 тем же матчером, что у дней 1-2 (tools/match_style.py).

    Кривая дня 4 (grade по перцентилям к 22/140/232) для кадров дня 5 не
    годится: кадры уже светлее, и она выбеливает кожу (проверено, sat падал до
    0.08 при 0.205 у эталона).

    Референс — не `_canon2_hero.png` (он на зелёном, и зелёный подмешивается в
    статистику волос и кожи, кадр уезжает в зелень), а вырезанный мастер
    `tools/refs/canon2_ref_stand_sm.webp`: маска фигуры берётся из альфы.
    """
    if weight <= 0:
        return rgb
    ref_im = Image.open(REF_KEYED).convert('RGBA')
    k = 900 / ref_im.width
    ref_im = ref_im.resize((900, round(ref_im.height * k)), Image.LANCZOS)
    ref = np.asarray(ref_im, dtype=np.float32) / 255.0
    fig_r = ref[..., 3] > 0.5
    sk_r, hr_r = skin_hair(ref[..., :3], fig_r)

    a = np.asarray(rgb, dtype=np.float32) / 255.0
    if fig is None:
        fig_a = np.ones(a.shape[:2], bool)
    else:
        fig_a = np.asarray(fig.resize(rgb.size, Image.LANCZOS)) > 128
        fig_a = np.asarray(Image.fromarray((fig_a * 255).astype(np.uint8))
                           .filter(ImageFilter.MaxFilter(3))) > 128
    sk_a, hr_a = skin_hair(a, fig_a)
    if sk_a.sum() < 500 or hr_a.sum() < 200:
        return rgb

    mu_sk, sd_sk = ref[..., :3][sk_r].mean(0), ref[..., :3][sk_r].std(0)
    mu_hr, sd_hr = ref[..., :3][hr_r].mean(0), ref[..., :3][hr_r].std(0)
    Lr = 0.299 * ref[..., 0] + 0.587 * ref[..., 1] + 0.114 * ref[..., 2]
    target = float((Lr[sk_r] > 0.935).mean())

    w_sk = MS.feather(sk_a)[..., None]
    out = MS.affine_match(a, sk_a, mu_sk, sd_sk, w_sk)
    L0 = 0.299 * out[..., 0] + 0.587 * out[..., 1] + 0.114 * out[..., 2]
    if (L0[sk_a] > 0.935).mean() > target * 1.15:
        out, _k, _f = MS.degloss(out, sk_a, w_sk, target)
    else:
        out, _k, _f = MS.gloss(out, sk_a, w_sk, target)
    w_hr = MS.feather(hr_a)[..., None]
    out = MS.affine_match(out, hr_a, mu_hr, sd_hr, w_hr)
    out = a * (1 - weight) + out * weight
    return Image.fromarray((np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8), 'RGB')


def skin_hair(a, fig):
    """Маски кожи и волос по насыщенности и порядку каналов (как в match_style)."""
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    mx, mn = a.max(2), a.min(2)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    skin = fig & (mx > 0.5) & (s > 0.05) & (s < 0.36) & (r > b)
    hair = fig & (mx > 0.50) & (s > 0.10) & (s < 0.65) & (r >= g * 1.005) & (g > b * 1.02)
    return skin, hair & ~skin


def to_canvas(rgb, bg):
    """3:4 холст как у канона: фигура по высоте 98 %, по центру.

    Поля добираются растяжкой краевых пикселей (edge pad), а не сплошной
    заливкой: у студийных кадров фон с мягкой виньеткой, и заливка давала
    заметный вертикальный шов на стыке с исходником.
    """
    W, H = PR.CANVAS
    k = (H * (1 - PR.TOP_PAD)) / rgb.height
    im = rgb.resize((max(1, round(rgb.width * k)), max(1, round(rgb.height * k))), Image.LANCZOS)
    if im.width >= W:
        left = (im.width - W) // 2
        im = im.crop((left, 0, left + W, im.height))
    else:
        arr = np.asarray(im)
        pad = W - im.width
        arr = np.pad(arr, ((0, 0), (pad // 2, pad - pad // 2), (0, 0)), mode='edge')
        im = Image.fromarray(arr, 'RGB')
    if im.height >= H:
        im = im.crop((0, im.height - H, W, im.height))
    else:
        arr = np.asarray(im)
        pad = H - im.height
        arr = np.pad(arr, ((pad, 0), (0, 0), (0, 0)), mode='edge')
        im = Image.fromarray(arr, 'RGB')
    return im


MATCH = 1.0   # доля канон-матча; 0 — оставить родной тон генерации


def build(tag, factor=HD.FACTOR):
    name = JOBS[tag]
    src = os.path.join(RAW, name)
    if not os.path.exists(src):
        print(f'{tag}: нет исходника {name}, пропуск')
        return None
    base = Image.open(src).convert('RGB')
    bg = backplate(base)
    print(f'{tag}: {name} {base.size} фон rgb({bg[0]},{bg[1]},{bg[2]}) ACNet x{factor:g}')
    mask = figure_mask(base, bg)
    big = PA.acnet_upscale(base, factor)
    art = big.convert('RGBA')
    art.putalpha(mask.resize(big.size, Image.LANCZOS))
    art = HD.sharpen(art)
    rgb = canon_match(art.convert('RGB'), weight=MATCH, fig=mask)
    rgb = to_canvas(rgb, bg)
    os.makedirs(OUT, exist_ok=True)
    dest = os.path.join(OUT, f'd5hd_{tag}.webp')
    rgb.save(dest, 'WEBP', quality=92, method=6)
    print(f'  -> {os.path.basename(dest)} {rgb.size} {os.path.getsize(dest) / 1e6:.2f} MB')
    return dest


def main(argv):
    global MATCH
    factor = HD.FACTOR
    args = list(argv)
    if '--no-match' in args:
        MATCH = 0.0
        args.remove('--no-match')
    if '--factor' in args:
        i = args.index('--factor')
        factor = float(args[i + 1])
        del args[i:i + 2]
    for tag in (args or list(JOBS)):
        build(tag, factor)


if __name__ == '__main__':
    main(sys.argv[1:])
