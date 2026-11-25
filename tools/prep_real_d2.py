# -*- coding: utf-8 -*-
"""Сборка арта второго дня в каноне 2.

Отличие от дня 1 только именами: assets/real/art_real_day2_sgN.webp (+ _sm) и
art_real_emo_day2_sgN_{blink,shy}.webp. Всё остальное — функции из prep_real.py
(ключ, despill, ACNet x2, холст 2340x3120, выравнивание эмоций по FFT).

Позы дня 1 не трогаются: у них свои файлы и своя геометрия.

    python3 tools/prep_real_d2.py
"""
import json
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_real as PR  # noqa: E402

ROOT = PR.ROOT
RAW = PR.RAW
OUT = PR.OUT

POSES = ('sg1', 'sg2', 'sg3', 'sg4')
MOODS = ('blink', 'shy')

# поза 1 второго дня — это сам эталон канона
BASE = {tag: os.path.join(RAW, f'_d2{tag}.png') for tag in POSES}
BASE['sg1'] = os.path.join(RAW, '_canon2_hero.png')

EMO = {mood: os.path.join(RAW, f'_d2g_{mood}_' + '{}' + '.png') for mood in MOODS}


def main():
    os.makedirs(OUT, exist_ok=True)
    log_path = os.path.join(OUT, 'align_day2.json')
    shifts = {}
    if os.path.exists(log_path):
        with open(log_path) as fh:
            shifts = json.load(fh)

    for tag in POSES:
        src = BASE[tag]
        if not os.path.exists(src):
            print(f'{tag}: нет исходника {src}, пропуск')
            continue
        print(f'{tag}:')
        base = Image.open(src).convert('RGB')
        art = PR.to_alpha_art(base)
        PR.save(art, os.path.join(OUT, f'art_real_day2_{tag}.webp'), master=True)
        PR.save(art, os.path.join(OUT, f'art_real_day2_{tag}_sm.webp'), master=False)

        for mood in MOODS:
            p = EMO[mood].format(tag)
            if not os.path.exists(p):
                print(f'  эмоция {mood}: нет {os.path.basename(p)}, пропуск')
                continue
            var = Image.open(p).convert('RGB')
            if var.size != base.size:
                var = var.resize(base.size, Image.LANCZOS)
            dx, dy = PR.best_shift(base, var)
            shifts[f'{tag}_{mood}'] = [dx, dy]
            canvas = Image.new('RGB', var.size, PR.plate_colour(var))
            canvas.paste(var, (dx, dy))
            emo = PR.to_alpha_art(canvas)
            PR.save(emo, os.path.join(OUT, f'art_real_emo_day2_{tag}_{mood}.webp'), master=False)

    with open(log_path, 'w') as fh:
        json.dump(shifts, fh, indent=1)
    print('сдвиги эмоций дня 2:', shifts)


if __name__ == '__main__':
    main()
