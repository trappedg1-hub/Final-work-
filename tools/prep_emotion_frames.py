# -*- coding: utf-8 -*-
"""Кадры-эмоции (моргание, смущённая улыбка) как полноценные кадры.

Генерация рисует ту же позу с тем же телом (проверено: сдвиг 0 px, корреляция
0.94–0.98), поэтому в игре это переключение кадра, а не наложение слоёв:
глаза закрываются её же нарисованными веками, шва и «двоения» нет.

Выход: assets/art_day1_sgN_<mood>.webp — 1170×1560, ключ тот же (green_dom).
"""
import os
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prep_arts import key_chroma, fill_edges, normalise  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.path.join(ROOT, 'images', 'raw_day1')
A = os.path.join(ROOT, 'assets')
SIZES = ((1170, ''), (1920, '@2x'))   # телефон / большие экраны; 1170 = как _sm у базы
MOODS = {'blink': '_blink_{tag}.png', 'shy': '_face_{tag}.png'}


def export(tag, mood, src_name):
    base = Image.open(os.path.join(RAW, f'_edit_{tag}.png')).convert('RGB')
    var = Image.open(os.path.join(RAW, src_name)).convert('RGB').resize(base.size, Image.LANCZOS)
    keyed, _ref = key_chroma(var)
    arr = np.array(keyed)
    rgb, alpha = arr[..., :3], arr[..., 3]
    filled = fill_edges(rgb, alpha)
    art = Image.fromarray(filled, 'RGB')
    art.putalpha(Image.fromarray(alpha, 'L'))
    # ровно та же геометрия, что у базового кадра (normalise -> 3840x5120 -> 1170x1560)
    full = normalise(art)
    for w_px, suffix in SIZES:
        im = full.resize((w_px, round(w_px * 4 / 3)), Image.LANCZOS)
        arr = np.array(im)
        out = os.path.join(A, f'art_emo_{tag}_{mood}{suffix}.webp')
        im.save(out, 'WEBP', quality=88, alpha_quality=100, method=6)
        al = arr[..., 3]; h, w = al.shape
        holes = float((al[int(h*0.30):int(h*0.75), int(w*0.30):int(w*0.70)] == 0).mean())
        print(f'{os.path.basename(out):34s} {w}x{h} {os.path.getsize(out)/1e6:.2f} MB  прозрачного {holes*100:.1f}%')


if __name__ == '__main__':
    for tag in ('sg1', 'sg2', 'sg3', 'sg4'):
        for mood, pat in MOODS.items():
            p = os.path.join(RAW, pat.format(tag=tag))
            if os.path.exists(p):
                export(tag, mood, p)
            else:
                print(f'нет {p}')
