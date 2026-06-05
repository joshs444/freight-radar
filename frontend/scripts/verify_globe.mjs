// Globe depth-fix verification. Loads the preview build, then captures the globe at three
// zooms — whole globe (check back-of-globe dots don't bleed through), default hemisphere,
// and deep zoom (the blink target: dots must stay solid). Wheel-drives the camera; no app
// code is modified.
//   node scripts/verify_globe.mjs
import { chromium } from 'playwright';

const URL = 'http://localhost:4173/';
const browser = await chromium.launch({
  channel: 'chrome',
  headless: true,
  args: ['--use-gl=angle', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--enable-webgl'],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));

await page.goto(URL, { waitUntil: 'networkidle', timeout: 45000 });
await page.waitForTimeout(6500);

const cx = 720, cy = 470; // globe center-ish
await page.mouse.move(cx, cy);

const wheel = async (dir, ticks) => {
  for (let i = 0; i < ticks; i++) {
    await page.mouse.wheel(0, dir);
    await page.waitForTimeout(40);
  }
  await page.waitForTimeout(1200);
};

// 1) whole globe — zoom OUT to minZoom to expose any back-hemisphere bleed-through
await wheel(120, 36);
await page.screenshot({ path: '/tmp/globe_whole.png' });

// 2) default hemisphere
await wheel(-120, 16);
await page.screenshot({ path: '/tmp/globe_default.png' });

// 3) deep zoom — the blink target; dots must be solid + crisp
await wheel(-120, 60);
await page.screenshot({ path: '/tmp/globe_zoomed.png' });

// stability sample: 5 frames ~140ms apart at deep zoom, no camera movement. Wind animates
// so frames differ globally; we only care the marker regions keep rendering (canvas alive).
const sizes = [];
for (let i = 0; i < 5; i++) {
  const b = await page.screenshot();
  sizes.push(b.length);
  await page.waitForTimeout(140);
}

const probe = await page.evaluate(() => {
  const canvases = [...document.querySelectorAll('canvas')];
  return { canvasCount: canvases.length, sizes: canvases.map((c) => `${c.width}x${c.height}`) };
});

console.log(JSON.stringify({ probe, errors, frameByteSizes: sizes }, null, 2));
await browser.close();
