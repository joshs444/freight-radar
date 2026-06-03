import { chromium } from 'playwright';
const b = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-gl=angle','--enable-unsafe-swiftshader'] });
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
await p.goto('http://localhost:4173/', { waitUntil: 'networkidle', timeout: 40000 });
await p.waitForTimeout(3000);
await p.click('.fr-card');                 // click top issue (Shanghai)
await p.waitForTimeout(3500);              // let flyTo + brief animate
const briefShown = await p.evaluate(() => !!document.querySelector('.fr-card.is-active .fr-card-brief'));
const zoom = await p.evaluate(() => window.__zoom || null);
console.log('brief expanded on active card:', briefShown);
await p.screenshot({ path: '/tmp/fr_click.png' });
await b.close();
