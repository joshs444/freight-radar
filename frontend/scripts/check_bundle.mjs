// Boot-critical bundle budget. Sums the gzipped size of everything the entry HTML loads
// up front — the entry script + every <link rel=modulepreload> chunk — and fails if it
// exceeds the budget. This enforces the lazy-map architecture: maplibre (~277KB gz) + deck
// (~91KB gz) are pulled by <Globe> via React.lazy and must stay OUT of the boot path, so a
// regression that re-preloads them (boot jumps ~188KB → ~460KB gz) fails here instead of
// silently tanking first paint. Run: `node scripts/check_bundle.mjs` (needs a built dist/).
import { readFileSync } from 'node:fs';
import { gzipSync } from 'node:zlib';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const dist = join(dirname(fileURLToPath(import.meta.url)), '..', 'dist');
const BUDGET_KB = 230; // current boot ≈ 188KB gz; headroom for growth, trips if maplibre returns

const html = readFileSync(join(dist, 'index.html'), 'utf8');
const entry = [...html.matchAll(/<script[^>]*src="([^"]+\.js)"/g)].map((m) => m[1]);
const preload = [...html.matchAll(/<link rel="modulepreload"[^>]*href="([^"]+\.js)"/g)].map(
  (m) => m[1]
);
const files = [...new Set([...entry, ...preload])].map((p) => p.replace(/^\.?\//, ''));

let total = 0;
const rows = files.map((f) => {
  const gz = gzipSync(readFileSync(join(dist, f))).length;
  total += gz;
  return `  ${(gz / 1024).toFixed(0).padStart(4)}KB  ${f}`;
});
const totalKb = total / 1024;

console.log(`boot-critical bundle (entry + modulepreload):\n${rows.join('\n')}`);
console.log(`bundle budget: ${totalKb.toFixed(0)}KB gz of ${BUDGET_KB}KB`);
if (totalKb > BUDGET_KB) {
  console.error(
    `✗ boot bundle ${totalKb.toFixed(0)}KB gz exceeds the ${BUDGET_KB}KB budget — is a heavy ` +
      `chunk (maplibre/deck) being preloaded at boot again?`
  );
  process.exit(1);
}
console.log('✓ boot stays under budget (heavy map chunks remain lazy)');
