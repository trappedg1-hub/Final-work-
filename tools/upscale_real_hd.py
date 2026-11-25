# -*- coding: utf-8 -*-
"""Пересборка арта дней 2-4 в HD (ACNet x4 + шарп + разворот свечения).

День 1 изначально собирался x4 и остаётся как есть, дни 2-4 шли через x2 —
отсюда «мыло» на телефоне. Здесь те же позы пересобираются общей HD-функцией
из tools/prep_hd.py, файлы перезаписываются на месте (имена не меняются).

    python3 tools/upscale_real_hd.py 2 3 4
    python3 tools/upscale_real_hd.py 4 sg2 sg4
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_hd as HD  # noqa: E402
import prep_real as PR  # noqa: E402

RAW = PR.RAW
OUT = PR.OUT
POSES = ('sg1', 'sg2', 'sg3', 'sg4')

# день -> исходник на позу (у дня 2 поза 1 — это эталон канона)
SRC = {
    '2': {'sg1': '_canon2_hero.png', 'sg2': '_d2sg2.png',
          'sg3': '_d2sg3.png', 'sg4': '_d2sg4.png'},
    '3': {tag: f'_d3{tag}.png' for tag in POSES},
    '4': {tag: f'_d4{tag}.png' for tag in POSES},
}


def main(argv):
    days = [a for a in argv if a in SRC] or list(SRC)
    tags = tuple(a for a in argv if a in POSES)
    os.makedirs(OUT, exist_ok=True)
    for day in days:
        for tag in (tags or POSES):
            name = SRC[day][tag]
            src = os.path.join(RAW, name)
            if not os.path.exists(src):
                print(f'{day}{tag}: нет исходника {name}, пропуск')
                continue
            print(f'{day}{tag}: {name}')
            base = Image.open(src).convert('RGB')
            art = HD.sharpen(HD.art_from(base, HD.FACTOR))
            PR.save(art, os.path.join(OUT, f'art_real_day{day}_{tag}.webp'), master=True)
            PR.save(art, os.path.join(OUT, f'art_real_day{day}_{tag}_sm.webp'), master=False)


if __name__ == '__main__':
    main(sys.argv[1:])
