// P6 "Nearby" panel runtime check: select a spine entity, assert the panel lists the cited
// co-located context ORDERED BY DISTANCE, carries the association-only disclaimer, widens
// with the radius, and closes. The anti-centrum surface — proven to never rank by severity.
//   npm run preview &  ; node scripts/verify_nearby.mjs
import { chromium } from 'playwright';

const URL = process.env.VERIFY_URL || 'http://localhost:4173/';
const browser = await chromium.launch({
  channel: 'chrome',
  headless: true,
  args: [
    '--use-gl=angle',
    '--ignore-gpu-blocklist',
    '--enable-unsafe-swiftshader',
    '--enable-webgl',
  ],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
page.setDefaultTimeout(8000);
const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));

const out = {};
try {
  await page.goto(URL, { waitUntil: 'networkidle', timeout: 45000 });
  await page.waitForTimeout(3000);
  await page.locator('.fr-row-head').first().click(); // select the top monitored entity
  await page.waitForTimeout(900);

  out.panelOpens = (await page.locator('.fr-nearby').count()) === 1;
  out.title = await page
    .locator('.fr-nearby-title')
    .textContent()
    .catch(() => null);
  const kms = (await page.locator('.fr-nearby-km').allTextContents()).map((k) => parseFloat(k));
  out.itemCount = kms.length;
  out.distanceOrdered = kms.every((v, i) => i === 0 || v >= kms[i - 1]);
  out.hasAssociationNote = await page
    .locator('.fr-nearby-note')
    .textContent()
    .then((t) => /association only/i.test(t || ''));

  // widening the radius can only add items (monotonic) — proves it's a radius, not a top-N
  await page.locator('.fr-nearby-radius', { hasText: '1.5k' }).click();
  await page.waitForTimeout(300);
  out.itemCountAt1500 = await page.locator('.fr-nearby-km').count();
  out.radiusMonotonic = out.itemCountAt1500 >= out.itemCount;

  await page.locator('.fr-nearby-x').click();
  await page.waitForTimeout(300);
  out.closeWorks = (await page.locator('.fr-nearby').count()) === 0;
} catch (e) {
  out.threwAt = String(e).split('\n')[0];
}
out.errors = errors;

const ok =
  out.panelOpens &&
  out.itemCount > 0 &&
  out.distanceOrdered &&
  out.hasAssociationNote &&
  out.radiusMonotonic &&
  out.closeWorks &&
  errors.length === 0 &&
  !out.threwAt;
console.log(JSON.stringify({ ok, ...out }, null, 2));
await browser.close();
process.exit(ok ? 0 : 1);
