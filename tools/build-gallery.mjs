// Static gallery bundle for Vercel: gallery/index.html + assets/*.webp -> dist/
import { cpSync, mkdirSync, rmSync, existsSync, copyFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, 'dist');

rmSync(dist, { recursive: true, force: true });
mkdirSync(join(dist, 'assets'), { recursive: true });

copyFileSync(join(root, 'gallery', 'index.html'), join(dist, 'index.html'));

const shots = ['sg1', 'sg2', 'sg3', 'sg4'].map(t => `art_day1_${t}.webp`);
for (const f of shots) {
  const src = join(root, 'assets', f);
  if (!existsSync(src)) throw new Error('missing assets/' + f);
  copyFileSync(src, join(dist, 'assets', f));
}
console.log('gallery bundled: index.html + ' + shots.length + ' webp');
