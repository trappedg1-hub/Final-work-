# -*- coding: utf-8 -*-
"""Сборка арта ЧЕТВЁРТОГО дня (волшебница) в каноне 2.

HD-пайплайн (ACNet x4 + шарп + разворот свечения) живёт в tools/prep_hd.py.

    python3 tools/prep_real_d4.py [sg1 sg2 sg3 sg4]
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_canon as PC  # noqa: E402
import prep_hd as HD  # noqa: E402
import prep_real as PR  # noqa: E402

RAW = PR.RAW
OUT = PR.OUT
POSES = ('sg1', 'sg2', 'sg3', 'sg4')


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
        art = canon().apply(art, soft=0.85)
        PR.save(art, os.path.join(OUT, f'art_real_day4_{tag}.webp'), master=True)
        PR.save(art, os.path.join(OUT, f'art_real_day4_{tag}_sm.webp'), master=False)


if __name__ == '__main__':
    main(sys.argv[1:])
