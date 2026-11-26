# -*- coding: utf-8 -*-
"""Сборка игровых кадров ПЯТОГО дня (розовое бикини, канон 2).

Источник — уже отобранная четвёрка из downloads/bikini (те же PNG, что лежат
в галерее на скачивание), поэтому игра и раздача всегда совпадают.

Пайплайн тот же, что у дня 4:
    зелёный ключ + разворот свечения (HD.deglow)
    -> ACNet x4 -> 3:4 холст 2340x3120 с альфой (PA.normalise)
    -> USM по RGB -> WebP q92

    python3 tools/prep_real_d5_game.py            # все четыре позы
    python3 tools/prep_real_d5_game.py sg3 sg4    # только выбранные
    python3 tools/prep_real_d5_game.py --factor 2
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_hd as HD  # noqa: E402
import prep_real as PR  # noqa: E402

ROOT = PR.ROOT
SRC_DIR = os.path.join(ROOT, 'downloads', 'bikini')

# тег в игре -> файл галереи
JOBS = {
    'sg1': 'pose1_ankles_crossed.png',      # щиколотки крест-накрест, туфли
    'sg2': 'pose2_leg_over_leg.png',        # нога на ногу, туфля в камеру
    'sg3': 'pose3_soles_to_player.png',     # босая, подошвы в игрока
    'sg4': 'pose4_legs_high_mega.png',      # завалилась, ноги вверх
}


def build(tag, factor=HD.FACTOR):
    name = JOBS[tag]
    src = os.path.join(SRC_DIR, name)
    if not os.path.exists(src):
        print(f'{tag}: нет исходника {name}, пропуск')
        return None
    print(f'{tag}: {name} ACNet x{factor:g}')
    base = Image.open(src).convert('RGB')
    art = HD.art_from(base, factor)
    art = HD.sharpen(art)
    os.makedirs(PR.OUT, exist_ok=True)
    PR.save(art, os.path.join(PR.OUT, f'art_real_day5_{tag}.webp'), master=True)
    PR.save(art, os.path.join(PR.OUT, f'art_real_day5_{tag}_sm.webp'), master=False)
    return tag


def main(argv):
    factor = HD.FACTOR
    args = list(argv)
    if '--factor' in args:
        i = args.index('--factor')
        factor = float(args[i + 1])
        del args[i:i + 2]
    for tag in (args or list(JOBS)):
        build(tag, factor)


if __name__ == '__main__':
    main(sys.argv[1:])
