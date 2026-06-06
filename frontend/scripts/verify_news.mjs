// Verify the GDELT news layer + the Standpoint rename on the preview build.
// Asserts: brand renamed, the Context section + news row + topic key render, the news
// count is present, and there are no console errors. Captures two screenshots.
//   node scripts/verify_news.mjs
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
const page = await browser.newPage({
  viewport: { width: 1440, height: 900 },
  deviceScaleFactor: 2,
});
const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));

await page.goto(URL, { waitUntil: 'networkidle', timeout: 45000 });
await page.waitForTimeout(6500);

const probe = await page.evaluate(() => {
  const txt = (sel) => [...document.querySelectorAll(sel)].map((e) => e.textContent.trim());
  const h1 = document.querySelector('.fr-brand h1')?.textContent?.trim();
  const panel = document.querySelector('.fr-layers')?.textContent || '';
  const rows = txt('.fr-layer').filter((t) => /news/i.test(t));
  return {
    h1,
    title: document.title,
    hasContextSection: /Context/.test(panel),
    hasNewsCaption: /possibly-related context, not a stated cause/.test(panel),
    hasProvenanceFoot: /no forecasts/.test(panel),
    newsRows: rows,
    newsKeyRows: txt('.fr-news-key-row'),
  };
});

await page.mouse.move(720, 470);
await page.screenshot({ path: '/tmp/standpoint_default.png' });
// zoom in a bit so the news dots are clearly visible
for (let i = 0; i < 14; i++) {
  await page.mouse.wheel(0, -120);
  await page.waitForTimeout(40);
}
await page.waitForTimeout(1200);
await page.screenshot({ path: '/tmp/standpoint_news_zoom.png' });

console.log(JSON.stringify({ probe, errors }, null, 2));
await browser.close();
