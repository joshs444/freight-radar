import { chromium } from 'playwright';
const url = process.argv[2] || 'http://localhost:4173/';
const browser = await chromium.launch({
  channel: 'chrome', headless: true,
  args: ['--use-gl=angle', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader'],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const logs = [];
page.on('console', (m) => logs.push(`[${m.type()}] ${m.text()}`));
page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}\n${e.stack || ''}`));
page.on('requestfailed', (r) => logs.push(`[reqfail] ${r.url()} :: ${r.failure()?.errorText}`));
page.on('response', (r) => { if (r.status() >= 400) logs.push(`[http ${r.status()}] ${r.url()}`); });
await page.goto(url, { waitUntil: 'load', timeout: 45000 });
await page.waitForTimeout(4000);
const root = await page.evaluate(() => ({
  rootHtml: document.getElementById('root')?.innerHTML?.slice(0, 600),
  bodyLen: document.body.innerHTML.length,
}));
console.log('=== LOGS ===');
console.log(logs.join('\n') || '(none)');
console.log('=== ROOT (first 600) ===');
console.log(root.rootHtml);
console.log('bodyLen:', root.bodyLen);
await browser.close();
