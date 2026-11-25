# -*- coding: utf-8 -*-
"""Сборка арта ЧЕТВЁРТОГО дня (волшебница) в каноне 2.

HD-пайплайн (ACNet x4 + шарп + разворот свечения) живёт в tools/prep_hd.py.

    python3 tools/prep_real_d4.py [sg1 sg2 sg3 sg4]
"""
import os
import sys

import numpy as np
import cv2
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_canon as PC  # noqa: E402
import prep_hd as HD  # noqa: E402
import prep_real as PR  # noqa: E402

RAW = PR.RAW
OUT = PR.OUT
POSES = ('sg1', 'sg2', 'sg3', 'sg4')



# ТОН КАНОНА. Новые генерации выходят заметно темнее и насыщеннее канона
# (L ~72-94 при 113-127 у дней 2-3, S ~64-83 при 38-69). Правка чисто
# цветокорректорская: тянем L-кривую по процентилям к канону и слегка
# приглушаем хрому — рисунок, поза и черты не меняются.
GRADE_PTS = ((0.05, 22.0), (0.50, 140.0), (0.95, 232.0))
CHROMA_K = 0.92
WARM = (1.5, 3.5)   # кожа канона теплее: чуть больше розового и жёлтого


def grade(art):
    if os.environ.get('D4_GRADE') == '0':
        return art
    arr = np.asarray(art.convert('RGBA'))
    rgb, al = arr[..., :3], arr[..., 3]
    lab = cv2.cvtColor(rgb, cv2.COLOR_RGB2LAB).astype(np.float32)
    L = lab[..., 0]
    body = al > 40
    q5, q50, q95 = np.percentile(L[body], [5, 50, 95]) if body.any() else (30.0, 120.0, 200.0)
    q5, q50, q95 = float(q5), float(q50), float(q95)
    # опорные точки прижимаем, чтобы кривая осталась монотонной
    q5 = max(2.0, min(q5, q50 - 2.0))
    q95 = min(253.0, max(q95, q50 + 2.0))
    xs = [0.0, q5, q50, q95, 255.0]
    ys = [0.0, GRADE_PTS[0][1], GRADE_PTS[1][1], GRADE_PTS[2][1], 255.0]
    lab[..., 0] = np.interp(L, xs, ys)
    lab[..., 1] = 128.0 + (lab[..., 1] - 128.0) * CHROMA_K + WARM[0]
    lab[..., 2] = 128.0 + (lab[..., 2] - 128.0) * CHROMA_K + WARM[1]
    out = cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)
    return Image.fromarray(np.dstack([out, al]), 'RGBA')

CS = None


def canon():
    global CS
    if CS is None:
        CS = PC.CanonStyle()
        print(CS.report())
    return CS


def main(argv):
    tags = tuple(a for a in argv if a in POSES) or POSES
    os.makedirs(OUT, exist_ok=True)
    for tag in tags:
        src = os.path.join(RAW, f'_d4{tag}.png')
        if not os.path.exists(src):
            print(f'{tag}: нет исходника {src}, пропуск')
            continue
        print(f'{tag}:')
        base = Image.open(src).convert('RGB')
        art = HD.sharpen(HD.art_from(base, HD.FACTOR))
        art = grade(art)
        # новые генерации дня 4 нарисованы уже в палитре канона: подгонка LAB
        # им не нужна и только выбеливает кожу (включается D4_CANON=1)
        if os.environ.get('D4_CANON') == '1':
            art = canon().apply(art, soft=0.85)
        PR.save(art, os.path.join(OUT, f'art_real_day4_{tag}.webp'), master=True)
        PR.save(art, os.path.join(OUT, f'art_real_day4_{tag}_sm.webp'), master=False)


if __name__ == '__main__':
    main(sys.argv[1:])
