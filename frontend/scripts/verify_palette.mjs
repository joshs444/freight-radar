// ⌘K command-palette runtime check: open via hotkey, assert it lists views/lenses/layers,
// filter by typing, toggle a layer, apply a lens (assert the URL gets ?lens=), and confirm
// Esc closes it. Pure behavior verification — no app code is modified.
//   node scripts/verify_palette.mjs
import { chromium } from 'playwright';

const URL = 'http://localhost:4173/';
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
page.setDefaultTimeout(4000);
const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));

await page.goto(URL, { waitUntil: 'networkidle', timeout: 45000 });
await page.waitForTimeout(2500);
await page.mouse.click(720, 12); // focus the page chrome (away from the globe canvas)

const out = {};
try {
  // 1) open with ⌘K (Meta+K)
  await page.keyboard.press('Meta+k');
  await page.waitForTimeout(400);
  out.opensOnCmdK = (await page.locator('.fr-cmdk').count()) === 1;

  // 2) lists groups: Go to (views), Load lens, Toggle
  const groups = await page.locator('.fr-cmdk-group').allTextContents();
  out.groups = groups;
  out.hasViews = groups.includes('Go to');
  out.hasLenses = groups.includes('Load lens');
  out.hasToggles = groups.some((g) => g.startsWith('Toggle'));
  out.rowCount = await page.locator('.fr-cmdk-row').count();

  // 3) filter narrows the list; 'tides' surfaces the tides toggle (and any lens that cites it)
  await page.locator('.fr-cmdk-input').fill('tides');
  await page.waitForTimeout(150);
  const filteredLabels = await page.locator('.fr-cmdk-row .fr-cmdk-label').allTextContents();
  out.filterTidesLabels = filteredLabels;
  out.filterSurfacesTides = filteredLabels.includes('tides');

  // 4) toggle the tides LAYER (the row whose label is exactly "tides") via click; the palette
  // stays open for toggles. Target by exact label so a tides-citing lens row can't be hit.
  const tidesRow = page
    .locator('.fr-cmdk-row', { has: page.locator('.fr-cmdk-label', { hasText: /^tides$/ }) })
    .first();
  const hintBefore = (await tidesRow.locator('.fr-cmdk-hint').textContent())?.trim();
  await tidesRow.click();
  await page.waitForTimeout(200);
  out.paletteStaysOpenOnToggle = (await page.locator('.fr-cmdk').count()) === 1;
  const hintAfter = (await tidesRow.locator('.fr-cmdk-hint').textContent())?.trim();
  out.toggleHintBeforeAfter = [hintBefore, hintAfter];
  out.toggleFlips = hintBefore !== hintAfter;

  // 5) apply the "Storm watch" lens (exact label) → URL carries ?lens=storm-watch, palette closes
  await page.locator('.fr-cmdk-input').fill('storm watch');
  await page.waitForTimeout(150);
  await page
    .locator('.fr-cmdk-row', { has: page.locator('.fr-cmdk-label', { hasText: /^Storm watch$/ }) })
    .first()
    .click();
  await page.waitForTimeout(600); // let the URL-sync effect run
  out.urlAfterLens = page.url();
  out.lensStampsUrl = page.url().includes('lens=storm-watch');
  out.paletteClosesOnNav = (await page.locator('.fr-cmdk').count()) === 0;
  // the stamp must SURVIVE the URL-sync effect (regression guard), then a manual toggle
  // clears it (the scene has diverged from the lens)
  await page.waitForTimeout(500);
  out.lensStampPersists = page.url().includes('lens=storm-watch');
  await page.keyboard.press('Meta+k');
  await page.waitForTimeout(200);
  await page.locator('.fr-cmdk-input').fill('vessels');
  await page.waitForTimeout(150);
  await page
    .locator('.fr-cmdk-row', { has: page.locator('.fr-cmdk-label', { hasText: /^vessels$/ }) })
    .first()
    .click();
  await page.waitForTimeout(400);
  out.toggleClearsLensStamp = !page.url().includes('lens=');
  await page.keyboard.press('Escape');

  // 6) Esc closes when reopened
  await page.keyboard.press('Meta+k');
  await page.waitForTimeout(150);
  const reopened = (await page.locator('.fr-cmdk').count()) === 1;
  await page.keyboard.press('Escape');
  await page.waitForTimeout(150);
  out.escCloses = reopened && (await page.locator('.fr-cmdk').count()) === 0;

  // 7) deep-link read: a shared #lens=source-ledger URL applies that lens on a FRESH load
  // (must be a new page — a hash change on the same SPA document won't remount React)
  const page2 = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  await page2.goto(URL + '#lens=source-ledger', { waitUntil: 'networkidle', timeout: 45000 });
  await page2.waitForTimeout(2800);
  const activeView = (await page2.locator('.fr-view-btn.on').first().textContent())?.trim();
  out.deepLinkActiveView = activeView;
  out.deepLinkAppliesLens = /Ledger/i.test(activeView || '');
  // the deep-linked stamp must persist on the fresh load too (the shareable round-trip)
  out.deepLinkUrlKeepsLens = page2.url().includes('lens=source-ledger');
  await page2.close();
} catch (e) {
  out.threwAt = String(e).split('\n')[0];
}
out.errors = errors;
console.log(JSON.stringify(out, null, 2));
await browser.close();
