# -*- coding: utf-8 -*-
"""Подгонка арта под статистику канона 2 (дни 2-3).

Почему это нужно: новые арты дня 4 генерировались отдельно и вышли заметно
другими по тону — темнее (средняя яркость ~77 против 120-138), пересыщеннее
(HSV S ~85 против 40-63) и резче (лапласиан ~47 против 27-37). На телефоне это
читалось как «другой стиль, особенно лицо».

Здесь тон приводится к канону в LAB: яркость выравнивается по среднему и
разбросу, хрома — по насыщенности канона, лишняя резкость гасится микроблюром.
Считаем только по непрозрачным пикселям фигуры, фон не трогаем.

    from prep_canon import CanonStyle
    cs = CanonStyle()
    art = cs.apply(art, soft=0.85)
"""
import os

import cv2
import numpy as np
from PIL import Image, ImageFilter

CANON_DAYS = ('2', '3')
POSES = ('sg1', 'sg2', 'sg3', 'sg4')


def _lab8(rgb):
    return cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8),
                        cv2.COLOR_RGB2LAB).astype(np.float32)


def _lab2rgb(lab):
    return cv2.cvtColor(np.clip(lab, 0, 255).astype(np.uint8), cv2.COLOR_LAB2RGB)


def _sharp(rgb, mask):
    g = cv2.cvtColor(np.clip(rgb, 0, 255).astype(np.uint8), cv2.COLOR_RGB2GRAY)
    return float(cv2.Laplacian(g, cv2.CV_32F)[mask].std())


class CanonStyle:
    def __init__(self, root=None):
        root = root or os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), 'assets', 'real')
        L, AB, SH = [], [], []
        for day in CANON_DAYS:
            for tag in POSES:
                p = os.path.join(root, f'art_real_day{day}_{tag}_sm.webp')
                if not os.path.exists(p):
                    continue
                a = np.asarray(Image.open(p).convert('RGBA')).astype(np.float32)
                m = a[..., 3] > 200
                if not m.any():
                    continue
                lab = _lab8(a[..., :3])
                L.append(lab[..., 0][m])
                AB.append(lab[..., 1:][m])
                SH.append(_sharp(a[..., :3], m))
        if not L:
            raise RuntimeError('канон не найден: нет артов дней 2-3')
        self.L = np.concatenate(L)
        self.AB = np.concatenate(AB)
        self.sharp = float(np.median(SH))
        self.l_mean, self.l_std = float(self.L.mean()), float(self.L.std())
        self.ab_mean = self.AB.mean(0)
        self.ab_std = self.AB.std(0)

    def report(self):
        return (f'канон: L {self.l_mean:.0f}±{self.l_std:.0f}, '
                f'ab {self.ab_mean.round(1)}, sharp {self.sharp:.0f}')

    def apply(self, art, soft=0.85):
        a = np.asarray(art).astype(np.float32)
        rgb, al = a[..., :3].copy(), a[..., 3]
        m = al > 16
        sel = al > 200
        if not sel.any():
            return art

        lab = _lab8(rgb)
        L, AB = lab[..., 0], lab[..., 1:]

        src_m, src_s = float(L[sel].mean()), float(L[sel].std())
        k = min(max(self.l_std / max(1e-3, src_s), 0.85), 1.25)
        k = 1.0 + (k - 1.0) * soft
        L = (L - src_m) * k + src_m + (self.l_mean - src_m) * soft

        ab_m = AB[sel].mean(0)
        ab_s = AB[sel].std(0)
        sc = np.clip(self.ab_std / np.maximum(1e-3, ab_s), 0.55, 1.15)
        sc = 1.0 + (sc - 1.0) * soft
        AB = ab_m + (AB - ab_m) * sc + (self.ab_mean - ab_m) * soft * 0.7

        out = _lab2rgb(np.dstack([L, AB])).astype(np.float32)
        res = Image.fromarray(np.clip(out, 0, 255).astype('uint8'), 'RGB')

        # лишняя резкость: у новых артов лапласиан почти вдвое выше канона
        cur = _sharp(out, sel)
        if cur > self.sharp * 1.12:
            res = res.filter(ImageFilter.GaussianBlur(0.8 * soft))

        res = res.convert('RGBA')
        res.putalpha(art.getchannel('A'))
        return res
