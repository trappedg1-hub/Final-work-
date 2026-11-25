// Static bundle for Vercel: index.html + assets/ -> dist/
import { cpSync, mkdirSync, rmSync, existsSync, statSync, readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = dirname(dirname(fileURLToPath(import.meta.url)));
const dist = join(root, 'dist');

rmSync(dist, { recursive: true, force: true });
mkdirSync(dist, { recursive: true });

for (const entry of ['index.html', 'assets']) {
  const src = join(root, entry);
  if (!existsSync(src)) throw new Error('missing ' + entry);
  cpSync(src, join(dist, entry), { recursive: true });
}

// Геометрию слоя эмоций подставляем из assets/real/emo_geo.json: раньше таблица
// в index.html дублировалась руками и расходилась с пересобранными патчами
// (слой ложился мимо глаз — «эмоции друг на друге»).
const geoPath = join(root, 'assets', 'real', 'emo_geo.json');
if (existsSync(geoPath)) {
  const geo = JSON.parse(readFileSync(geoPath, 'utf8'));
  const body = Object.entries(geo)
    .map(([k, v]) => `  '${k}': [${v.map((n) => Number(n)).join(', ')}]`)
    .join(',\n');
  const idxPath = join(dist, 'index.html');
  const html = readFileSync(idxPath, 'utf8');
  const next = html.replace(/const EMO_GEO_REAL = \{[\s\S]*?\n\};/,
    'const EMO_GEO_REAL = {\n' + body + '\n};');
  if (next !== html) {
    writeFileSync(idxPath, next);
    console.log('emo geo: подставлена из emo_geo.json (' + Object.keys(geo).length + ' поз)');
  }
}

const bytes = statSync(join(dist, 'index.html')).size;
console.log('bundled dist/ — index.html ' + bytes + ' B, assets copied');
