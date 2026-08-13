/**
 * Copy the recorded run into the web app's static assets.
 *
 * The engine owns the fixture and the dashboard consumes it, so it lives in one
 * place and is copied at build time rather than being duplicated in the repo
 * and drifting. Runs in `prebuild` and `predev`.
 */
import { copyFileSync, existsSync, mkdirSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const src = resolve(here, '../../engine/data/runs/demo-run.json');
const dest = resolve(here, '../public/demo-run.json');

if (!existsSync(src)) {
  console.error(
    `\n  Missing ${src}\n  Generate it first:  cd engine && antivenom demo --write\n`,
  );
  process.exit(1);
}

mkdirSync(dirname(dest), { recursive: true });
copyFileSync(src, dest);
console.log(`synced demo-run.json -> public/`);
