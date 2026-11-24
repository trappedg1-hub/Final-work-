// Готовит сгенерированные кресла: вырезает белый фон заливкой от границ,
// обрезает по контенту и сохраняет в assets/chair_<tier>.webp (RGBA).
import sharp from 'sharp';
import path from 'node:path';
import fs from 'node:fs';

const ROOT = process.env.ROOT || path.resolve(import.meta.dirname, '..');
const JOBS = [
  { src: 'assets/_gen_chair1.png', out: 'assets/chair_office.webp' },
  { src: 'assets/_gen_chair2.png', out: 'assets/chair_pink.webp' },
  { src: 'assets/_gen_chair3.png', out: 'assets/chair_throne.webp' },
];

const TOL = 46; // насколько пиксель должен отличаться от белого, чтобы считаться «стулом»

for (const job of JOBS) {
  const inPath = path.join(ROOT, job.src);
  const { data, info } = await sharp(inPath).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
  const { width: w, height: h, channels: c } = info;

  // маска «не фон»: flood fill от рамки по почти-белым пикселям
  const bg = new Uint8Array(w * h);
  const stack = [];
  const isWhite = (i) => {
    const r = data[i * c], g = data[i * c + 1], b = data[i * c + 2];
    const d = Math.max(255 - r, 255 - g, 255 - b);
    return d < TOL;
  };
  for (let x = 0; x < w; x++) { stack.push(x, 0, x, h - 1); }
  for (let y = 0; y < h; y++) { stack.push(0, y, w - 1, y); }
  while (stack.length) {
    const y = stack.pop(), x = stack.pop();
    if (x < 0 || y < 0 || x >= w || y >= h) continue;
    const i = y * w + x;
    if (bg[i] || !isWhite(i)) continue;
    bg[i] = 1;
    stack.push(x + 1, y, x - 1, y, x, y + 1, x, y - 1);
  }

  // альфа: 0 на фоне, плавная кромка на 1 px
  const alpha = new Uint8Array(w * h);
  for (let i = 0; i < w * h; i++) alpha[i] = bg[i] ? 0 : 255;
  const soft = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const i = y * w + x;
      if (alpha[i] === 0) { soft[i] = 0; continue; }
      let sum = 0, n = 0;
      for (let dy = -1; dy <= 1; dy++) for (let dx = -1; dx <= 1; dx++) {
        const nx = x + dx, ny = y + dy;
        if (nx < 0 || ny < 0 || nx >= w || ny >= h) continue;
        sum += alpha[ny * w + nx]; n++;
      }
      soft[i] = Math.round(sum / n);
    }
  }

  // bbox по маске
  let x0 = w, y0 = h, x1 = -1, y1 = -1;
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) {
    if (soft[y * w + x] > 8) {
      if (x < x0) x0 = x; if (x > x1) x1 = x;
      if (y < y0) y0 = y; if (y > y1) y1 = y;
    }
  }
  const pad = Math.round(Math.min(x1 - x0, y1 - y0) * 0.02);
  x0 = Math.max(0, x0 - pad); y0 = Math.max(0, y0 - pad);
  x1 = Math.min(w - 1, x1 + pad); y1 = Math.min(h - 1, y1 + pad);
  const cw = x1 - x0 + 1, chh = y1 - y0 + 1;

  const out = Buffer.alloc(cw * chh * 4);
  for (let y = 0; y < chh; y++) for (let x = 0; x < cw; x++) {
    const si = (y + y0) * w + (x + x0);
    const di = (y * cw + x) * 4;
    out[di] = data[si * c]; out[di + 1] = data[si * c + 1]; out[di + 2] = data[si * c + 2];
    out[di + 3] = soft[si];
  }

  await sharp(out, { raw: { width: cw, height: chh, channels: 4 } })
    .resize({ height: Math.min(1200, chh), withoutEnlargement: false, kernel: 'lanczos3' })
    .webp({ quality: 90, alphaQuality: 100, effort: 6 })
    .toFile(path.join(ROOT, job.out));

  const st = fs.statSync(path.join(ROOT, job.out));
  const meta = await sharp(path.join(ROOT, job.out)).metadata();
  console.log(`${job.out}: ${meta.width}x${meta.height} (${(st.size / 1024).toFixed(0)} KB)`);
}
