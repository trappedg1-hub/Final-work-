# -*- coding: utf-8 -*-
"""Кропы головы дня 4 под генерацию мимики.

Кропы берутся из мастеров (2340 px) по тем же BOX, что и в prep_eyes.py —
иначе слои эмоций не совпадут с базой. Ширина 820 px: лицо в кропе ~430 px,
и в кадр 1170x1560 оно ложится без растяжения.

    python3 tools/prep_faces_crop_d4.py [sg2 sg4]
"""
import os
import sys

from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_eyes as PE  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'images', 'raw_real')
FACES = os.path.join(RAW, 'faces')
ASSETS = os.path.join(ROOT, 'assets', 'real')
MASTER = (2340, 3120)
WIDTH = 820


def main(argv):
    tags = tuple(a for a in argv if a in ('sg1', 'sg2', 'sg3', 'sg4')) or ('sg1', 'sg2', 'sg3', 'sg4')
    os.makedirs(FACES, exist_ok=True)
    W, H = MASTER
    for tag in tags:
        art = Image.open(os.path.join(ASSETS, f'art_real_day4_{tag}.webp')).convert('RGBA')
        art = art.resize(MASTER, Image.LANCZOS)
        x0, y0, x1, y1 = PE.BOX['4' + tag]
        crop = art.crop((round(W * x0), round(H * y0), round(W * x1), round(H * y1)))
        k = WIDTH / crop.width
        crop = crop.resize((WIDTH, round(crop.height * k)), Image.LANCZOS)
        dest = os.path.join(FACES, f'face_4{tag}.png')
        crop.save(dest)
        print(f'{tag}: {crop.size} -> {os.path.basename(dest)}')


if __name__ == '__main__':
    main(sys.argv[1:])
