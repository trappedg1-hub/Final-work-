// Static bundle for Vercel: index.html + assets/ -> dist/
import { cpSync, mkdirSync, rmSync, existsSync, statSync } from 'node:fs';
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

const bytes = statSync(join(dist, 'index.html')).size;
console.log('bundled dist/ — index.html ' + bytes + ' B, assets copied');
