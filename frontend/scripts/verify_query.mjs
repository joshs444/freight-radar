// Headless verification for the Data view (in-browser DuckDB-WASM SQL console). Loads the
// preview build at #v=data, waits for the engine to instantiate + the first canned query to
// run, and asserts the results table renders rows with zero console errors. This gates the
// feature: the SQL console must prove itself in a real browser before it ships.
//   npm run preview &  ; node scripts/verify_query.mjs
import { chromium } from 'playwright';

const URL = (process.env.VERIFY_URL || 'http://localhost:4173/') + '#v=data';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));

await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 60000 });
await page.waitForSelector('.fr-query', { timeout: 60000 });

let snap = { rows: 0, views: 0, status: '', ready: '0' };
for (let i = 0; i < 90; i++) {
  snap = await page.evaluate(() => ({
    rows: document.querySelectorAll('[data-testid="fr-query-table"] tbody tr').length,
    views: document.querySelectorAll('.fr-query-views li').length,
    status: document.querySelector('.fr-query-sub')?.textContent || '',
    ready: document.querySelector('.fr-query')?.getAttribute('data-ready') || '0',
  }));
  if (snap.ready === '1' && snap.rows > 0) break;
  await page.waitForTimeout(1000);
}

// run a second query (a cross-source JOIN) to prove interactivity, not just the auto-run
await page.evaluate(() => {
  const btns = [...document.querySelectorAll('.fr-query-ex')];
  const join = btns.find((b) => /flags/i.test(b.textContent || ''));
  join?.click();
});
await page.waitForTimeout(3000);
const joinRows = await page.evaluate(
  () => document.querySelectorAll('[data-testid="fr-query-table"] tbody tr').length,
);

const real = errors.filter((e) => !/favicon|net::ERR_ABORTED.*favicon/i.test(e));
const ok = snap.ready === '1' && snap.rows > 0 && snap.views > 0 && joinRows > 0 && real.length === 0;
console.log(
  JSON.stringify(
    { ok, autoRunRows: snap.rows, joinRows, views: snap.views, status: snap.status.slice(0, 90), errors: real },
    null,
    2,
  ),
);
await browser.close();
process.exit(ok ? 0 : 1);
