// Headless screenshot receipt for the globe. Drives system Chrome with WebGL on.
//   node scripts/shot.mjs <url> <outfile>
import { chromium } from 'playwright';

const url = process.argv[2] || 'http://localhost:4173/';
const out = process.argv[3] || '/tmp/fr_shot.png';

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
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });

const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));

await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
// let the globe tiles, fonts, and deck layers settle + a couple pulse frames
await page.waitForTimeout(6500);

// quick DOM/canvas assertions
const probe = await page.evaluate(() => {
  const canvases = [...document.querySelectorAll('canvas')];
  const cards = document.querySelectorAll('.fr-card').length;
  const title = document.querySelector('.fr-head h1')?.textContent?.trim();
  const asof = document.querySelector('.fr-asof b')?.textContent?.trim();
  return {
    canvasCount: canvases.length,
    canvasSizes: canvases.map((c) => `${c.width}x${c.height}`),
    cards,
    title,
    asof,
  };
});

await page.screenshot({ path: out });
console.log(JSON.stringify({ probe, errors, out }, null, 2));
await browser.close();
