// Headless verification for the Ledger view (the "show your work" source ledger). Loads
// the preview build at #v=ledger and asserts the catalog table renders rows with tier
// badges and zero console errors.
//   npm run preview &  ; node scripts/verify_ledger.mjs
import { chromium } from 'playwright';

const URL = (process.env.VERIFY_URL || 'http://localhost:4173/') + '#v=ledger';
const browser = await chromium.launch({ channel: 'chrome', headless: true });
const page = await browser.newPage({ viewport: { width: 1280, height: 900 } });
const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));

try {
  await page.goto(URL, { waitUntil: 'domcontentloaded', timeout: 45000 });
  await page.waitForSelector('[data-testid="fr-ledger-table"] tbody tr', { timeout: 30000 });
  const rows = await page.evaluate(
    () => document.querySelectorAll('[data-testid="fr-ledger-table"] tbody tr').length,
  );
  const tierBadges = await page.evaluate(() => document.querySelectorAll('.fr-tier').length);
  const real = errors.filter((e) => !/favicon/i.test(e));
  const ok = rows > 0 && tierBadges > 0 && real.length === 0;
  console.log(JSON.stringify({ ok, rows, tierBadges, errors: real }));
  await browser.close();
  process.exit(ok ? 0 : 1);
} catch (e) {
  console.log(JSON.stringify({ ok: false, error: String(e.message || e), errors }));
  await browser.close();
  process.exit(1);
}
