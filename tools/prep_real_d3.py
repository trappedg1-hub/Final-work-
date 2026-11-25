# -*- coding: utf-8 -*-
"""Сборка арта ТРЕТЬЕГО дня в каноне 2 (йога в офисе).

Отличие от дня 2 только именами: images/raw_real/_d3sgN.png ->
assets/real/art_real_day3_sgN.webp (+ _sm). Эмоции здесь НЕ собираются:
слой мимики делает tools/prep_eyes.py из кропов головы _d3f2_{mood}_{tag}.png
(полнокадровые генераты для дней 1-2 вёрстке не нужны).

    python3 tools/prep_real_d3.py
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_real as PR  # noqa: E402

RAW = PR.RAW
OUT = PR.OUT
POSES = ('sg1', 'sg2', 'sg3', 'sg4')


def main():
    os.makedirs(OUT, exist_ok=True)
    for tag in POSES:
        src = os.path.join(RAW, f'_d3{tag}.png')
        if not os.path.exists(src):
            print(f'{tag}: нет исходника {src}, пропуск')
            continue
        print(f'{tag}:')
        base = Image.open(src).convert('RGB')
        art = PR.to_alpha_art(base)
        PR.save(art, os.path.join(OUT, f'art_real_day3_{tag}.webp'), master=True)
        PR.save(art, os.path.join(OUT, f'art_real_day3_{tag}_sm.webp'), master=False)


if __name__ == '__main__':
    main()
