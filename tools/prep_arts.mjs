// Prep новых кадров: chroma key от границ -> мягкая альфа -> despill ->
// лёгкий апскейл до 1560 px + unsharp -> холст 3:4 1560x2080 -> WebP.
// Правило: фон удаляется только если он связан с рамкой ИЛИ почти точно совпал
// с эталоном плашки (эталон = медиана угловых патчей). Глаза/одежда не трогаются.
import sharp from 'sharp';
import path from 'node:path';
import fs from 'node:fs';

const ROOT = process.env.ROOT || path.resolve(import.meta.dirname, '..');
const CANVAS = { w: 1560, h: 2080 };
const TOP_PAD = 0.02;
const FLOOD = 110;   // сумма |dr|+|dg|+|db| до эталона плашки
const TIGHT = 85;

const JOBS = {
  sg1: '_edit_sg1.png',
  sg2: '_edit_sg2.png',
  sg3: '_edit_sg3.png',
  sg4: '_edit_sg4.png',
};

function keyChroma(data, w, h, c) {
  // эталон плашки — медиана четырёх угловых патчей
  const sample = (x0, y0) => {
    const rs = [], gs = [], bs = [];
    for (let y = y0; y < y0 + 30; y++) for (let x = x0; x < x0 + 30; x++) {
      const i = (y * w + x) * c;
      rs.push(data[i]); gs.push(data[i + 1]); bs.push(data[i + 2]);
    }
    const med = (a) => a.sort((p, q) => p - q)[a.length >> 1];
    return [med(rs), med(gs), med(bs)];
  };
  const corners = [sample(6, 6), sample(w - 36, 6), sample(6, h - 36), sample(w - 36, h - 36)];
  const ref = [0, 1, 2].map(k => Math.round(corners.reduce((s, p) => s + p[k], 0) / 4));

  const dist = new Uint16Array(w * h);
  for (let i = 0; i < w * h; i++) {
    const j = i * c;
    dist[i] = Math.abs(data[j] - ref[0]) + Math.abs(data[j + 1] - ref[1]) + Math.abs(data[j + 2] - ref[2]);
  }
  const bg = new Uint8Array(w * h);
  const stack = [];
  for (let x = 0; x < w; x++) { stack.push(x, 0, x, h - 1); }
  for (let y = 0; y < h; y++) { stack.push(0, y, w - 1, y); }
  while (stack.length) {
    const y = stack.pop(), x = stack.pop();
    if (x < 0 || y < 0 || x >= w || y >= h) continue;
    const i = y * w + x;
    if (bg[i] || dist[i] > FLOOD) continue;
    bg[i] = 1;
    stack.push(x + 1, y, x - 1, y, x, y + 1, x, y - 1);
  }
  for (let i = 0; i < w * h; i++) if (dist[i] < TIGHT) bg[i] = 1;

  // альфа + мягкая кромка (1 проход box-блюра 3x3)
  const a0 = new Uint8Array(w * h);
  for (let i = 0; i < w * h; i++) a0[i] = bg[i] ? 0 : 255;
  const out = Buffer.alloc(w * h * 4);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x, si = i * c, di = i * 4;
      let sum = 0, n = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const nx = x + dx, ny = y + dy;
        if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
        sum += a0[ny * w + nx]; n++;
      }
      let a = Math.round(sum / n);
      a = Math.max(0, Math.min(255, Math.round((a - 12) / (255 - 24) * 255)));
      let r = data[si], g = data[si + 1], b = data[si + 2];
      // despill у кромки: зелёный не должен перебивать максимум из r/b
      if (a < 250) {
        const mx = Math.max(r, b);
        if (g > mx) g = mx;
      }
      out[di] = r; out[di + 1] = g; out[di + 2] = b; out[di + 3] = a;
    }
  }
  return { buf: out, ref };
}

function bbox(buf, w, h) {
  let x0 = w, y0 = h, x1 = -1, y1 = -1;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    if (buf[(y * w + x) * 4 + 3] > 8) {
      if (x < x0) x0 = x; if (x > x1) x1 = x;
      if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
  }
  return { x0, y0, x1, y1 };
}

for (const tag of process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(JOBS)) {
  const src = path.join(ROOT, 'images', 'raw_day1', JOBS[tag]);
  const { data, info } = await sharp(src).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const { width: w, height: h, channels: c } = info;
  const { buf, ref } = keyChroma(data, w, h, c);
  const bb = bbox(buf, w, h);
  const pw = bb.x1 - bb.x0 + 1, ph = bb.y1 - bb.y0 + 1;

  const cut = await sharp(buf, { raw: { width: w, height: h, channels: 4 } })
    .extract({ left: bb.x0, top: bb.y0, width: pw, height: ph })
    .png().toBuffer();

  // масштаб: 3:4 с воздухом сверху, по ширине не шире холста
  const kFit = (CANVAS.h * (1 - TOP_PAD)) / ph;
  const kMax = CANVAS.w / pw;
  const k = Math.min(kFit, kMax) * 1.0;
  const upW = Math.round(pw * k), upH = Math.round(ph * k);
  const up = await sharp(cut).resize({ width: upW, height: upH, kernel: 'lanczos3' })
    .sharpen({ sigma: 0.7, m1: 0.6, m2: 0.4 }).png().toBuffer();

  let layer = up, lw = upW, lh = upH;
  if (lw > CANVAS.w) {                       // шире 3:4 — подрезаем бока симметрично
    const left = Math.round((lw - CANVAS.w) / 2);
    layer = await sharp(up).extract({ left, top: 0, width: CANVAS.w, height: lh }).png().toBuffer();
    lw = CANVAS.w;
  }

  const dest = path.join(ROOT, 'assets', `art_day1_${tag}.webp`);
  await sharp({ create: { width: CANVAS.w, height: CANVAS.h, channels: 4, background: { r: 0, g: 0, b: 0, alpha: 0 } } })
    .composite([{ input: layer, left: Math.round((CANVAS.w - lw) / 2), top: CANVAS.h - lh }])
    .webp({ quality: 92, alphaQuality: 100, effort: 6 })
    .toFile(dest);

  console.log(`${tag}: plate rgb(${ref.join(',')}) bbox ${pw}x${ph} -> ${CANVAS.w}x${CANVAS.h} `
    + `${(fs.statSync(dest).size / 1e6).toFixed(2)} MB`);
}
