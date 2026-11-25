# -*- coding: utf-8 -*-
"""Кропы головы под генерацию эмоций — в высоком разрешении, из мастеров.

Раньше эмоции рисовались с кропа 560 px и при сборке растягивались — отсюда
«низкополигональное» лицо. Здесь кроп берётся из мастера (2340 px) и
приводится к 820 px: лицо занимает ~450 px, и в кадр 1170x1560 оно ложится
без растяжения.

    python3 tools/prep_faces_crop.py
"""
import os

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'images', 'raw_real')
OUT = os.path.join(ROOT, 'images', 'raw_real', 'faces')
MASTER = (2340, 3120)      # холст мастеров обоихдней
WIDTH = 820                # ширина кропа на выходе

# кропы в долях кадра: (x0, y0, x1, y1)
BOX = {
    '1sg1': (0.320, 0.010, 0.640, 0.240),
    '1sg2': (0.310, 0.010, 0.620, 0.235),
    '1sg3': (0.360, 0.008, 0.670, 0.238),
    '1sg4': (0.365, 0.008, 0.675, 0.238),
    '2sg1': (0.300, 0.030, 0.700, 0.250),
    '2sg2': (0.355, 0.030, 0.725, 0.240),
    '2sg3': (0.345, 0.025, 0.715, 0.245),
    '2sg4': (0.375, 0.025, 0.725, 0.245),
    '3sg1': (0.520, 0.060, 0.860, 0.300),
    '3sg2': (0.050, 0.100, 0.360, 0.330),
    '3sg3': (0.360, 0.040, 0.660, 0.270),
    '3sg4': (0.360, 0.040, 0.680, 0.280),
}
SRC = {
    '1sg1': 'art_real_day1_sg1.webp',
    '1sg2': 'art_real_day1_sg2.webp',
    '1sg3': 'art_real_day1_sg3.webp',
    '1sg4': 'art_real_day1_sg4.webp',
    '2sg1': 'art_real_day2_sg1.webp',
    '2sg2': 'art_real_day2_sg2.webp',
    '2sg3': 'art_real_day2_sg3.webp',
    '2sg4': 'art_real_day2_sg4.webp',
    '3sg1': 'art_real_day3_sg1.webp',
    '3sg2': 'art_real_day3_sg2.webp',
    '3sg3': 'art_real_day3_sg3.webp',
    '3sg4': 'art_real_day3_sg4.webp',
}


def main():
    os.makedirs(OUT, exist_ok=True)
    for key, rel in SRC.items():
        art = Image.open(os.path.join(ROOT, 'assets', 'real', rel)).convert('RGBA')
        art = art.resize(MASTER, Image.LANCZOS)
        W, H = MASTER
        x0, y0, x1, y1 = BOX[key]
        crop = art.crop((round(W * x0), round(H * y0), round(W * x1), round(H * y1)))
        k = WIDTH / crop.width
        crop = crop.resize((WIDTH, round(crop.height * k)), Image.LANCZOS)
        flat = Image.new('RGB', crop.size, (13, 178, 38))
        flat.paste(crop, (0, 0), crop)
        out = os.path.join(OUT, f'face_{key}.png')
        flat.save(out)
        print(f'face_{key}.png {flat.size}')
    print('готово')


if __name__ == '__main__':
    main()
