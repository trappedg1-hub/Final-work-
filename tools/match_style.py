"""Доводка кадра под канон 2 — один детерминированный проход.

Что делает:
  1. Кожа: линейное совмещение среднего и разброса по каналам со статистикой эталона
     (фарфор, низкая насыщенность) — под мягкой маской.
  2. Глянец: подъём верхних тонов кожи к белому, чтобы доля бликов совпала с эталоном.
  3. Волосы: подтяжка тона к платине эталона.

Без генерации, без изменения формы и деталей. Один и тот же проход применяется
ко всем кадрам набора, поэтому палитра едет 1:1.

    python3 tools/match_style.py images/raw_real/_sg1.png --out /tmp/x.png
"""

import sys
import numpy as np
from PIL import Image, ImageFilter

REF = 'images/raw_real/_canon2_hero.png'
W = 900


def _arr(path, width=W):
    im = Image.open(path).convert('RGB')
    w, h = im.size
    if w != width:
        im = im.resize((width, round(h * width / w)), Image.LANCZOS)
    return np.asarray(im).astype(np.float32) / 255.0


def masks(a):
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    fig = ~((g > 0.45) & (g > r * 1.25) & (g > b * 1.25))
    mx, mn = a.max(2), a.min(2)
    s = np.where(mx > 1e-6, (mx - mn) / np.maximum(mx, 1e-6), 0)
    skin = fig & (mx > 0.5) & (s > 0.05) & (s < 0.36) & (r > b)
    hair = fig & (mx > 0.50) & (s > 0.10) & (s < 0.65) & (r >= g * 1.005) & (g > b * 1.02)
    return fig, skin, hair & ~skin


def feather(mask, radius=6, gain=4.0):
    m = Image.fromarray((mask * 255).astype(np.uint8), 'L').filter(ImageFilter.GaussianBlur(radius))
    return np.clip(np.asarray(m).astype(np.float32) / 255.0 * gain, 0, 1)


def affine_match(a, mask, mu_t, sd_t, weight):
    mu, sd = a[mask].mean(0), a[mask].std(0)
    gain = np.where(sd > 1e-4, np.clip(sd_t / np.maximum(sd, 1e-4), 0.6, 1.6), 1.0)
    out = a * gain + (mu_t - mu * gain)
    return a * (1 - weight) + np.clip(out, 0, 1) * weight


def gloss(a, mask, weight, target_frac, iters=6):
    """Поднимает верхние тона кожи, пока доля бликов не совпадёт с эталоном."""
    L = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    for k in (0.0, 0.12, 0.2, 0.28, 0.36, 0.45, 0.55, 0.7):
        hi = np.clip((L - 0.70) / 0.30, 0, 1) ** 2
        cand = np.clip(a + (1.0 - a) * (hi * k)[..., None] * weight, 0, 1)
        Lc = 0.299 * cand[..., 0] + 0.587 * cand[..., 1] + 0.114 * cand[..., 2]
        frac = (Lc[mask] > 0.935).mean()
        if frac >= target_frac:
            return cand, k, frac
    return cand, k, frac


def degloss(a, mask, weight, target_frac):
    """Если бликов больше, чем в эталоне, — срезает верхние тона до цели."""
    L = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    hi = np.clip((L - 0.70) / 0.30, 0, 1) ** 2
    best, best_k, best_frac = a, 0.0, (L[mask] > 0.935).mean()
    for k in np.linspace(0.05, 0.85, 17):
        cand = np.clip(a - a * (hi * k)[..., None] * weight, 0, 1)
        Lc = 0.299 * cand[..., 0] + 0.587 * cand[..., 1] + 0.114 * cand[..., 2]
        frac = (Lc[mask] > 0.935).mean()
        if abs(frac - target_frac) < abs(best_frac - target_frac):
            best, best_k, best_frac = cand, float(k), frac
    return best, best_k, best_frac


def measure(a, mask, name):
    L = 0.299 * a[..., 0] + 0.587 * a[..., 1] + 0.114 * a[..., 2]
    print(f"{name:12s} блики={(L[mask]>0.935).mean()*100:4.1f}%  контраст={L[mask].std():.3f}  "
          f"кожаRGB=({a[mask][:,0].mean():.3f},{a[mask][:,1].mean():.3f},{a[mask][:,2].mean():.3f})")


def grade(a, ref, target_frac=None):
    fig_r, sk_r, hr_r = masks(ref)
    fig_a, sk_a, hr_a = masks(a)
    mu_sk, sd_sk = ref[sk_r].mean(0), ref[sk_r].std(0)
    mu_hr, sd_hr = ref[hr_r].mean(0), ref[hr_r].std(0)
    if target_frac is None:
        Lr = 0.299 * ref[..., 0] + 0.587 * ref[..., 1] + 0.114 * ref[..., 2]
        target_frac = (Lr[sk_r] > 0.935).mean()
    w_sk = feather(sk_a)[..., None]
    out = affine_match(a, sk_a, mu_sk, sd_sk, w_sk)
    L0 = 0.299 * out[..., 0] + 0.587 * out[..., 1] + 0.114 * out[..., 2]
    if (L0[sk_a] > 0.935).mean() > target_frac * 1.15:
        out, k, frac = degloss(out, sk_a, w_sk, target_frac)
    else:
        out, k, frac = gloss(out, sk_a, w_sk, target_frac)
    w_hr = feather(hr_a)[..., None]
    out = affine_match(out, hr_a, mu_hr * 1.0, sd_hr, w_hr)
    return out, k, frac, target_frac


if __name__ == '__main__':
    src = sys.argv[1]
    out_path = sys.argv[sys.argv.index('--out') + 1] if '--out' in sys.argv else None
    ref = _arr(REF)
    a = _arr(src)
    fig_r, sk_r, hr_r = masks(ref)
    fig_a, sk_a, hr_a = masks(a)
    measure(ref, sk_r, 'эталон')
    measure(a, sk_a, 'до')
    g, k, frac, tgt = grade(a, ref)
    measure(g, sk_a, 'после')
    print(f'глянец k={k:.2f}, блики {frac*100:.1f}% при цели {tgt*100:.1f}%')
    if out_path:
        Image.fromarray((g * 255 + 0.5).astype(np.uint8)).resize(Image.open(src).size, Image.LANCZOS).save(out_path)
        print('сохранено:', out_path)
