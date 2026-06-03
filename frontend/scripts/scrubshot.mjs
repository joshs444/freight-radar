import { chromium } from 'playwright';
const b = await chromium.launch({ channel: 'chrome', headless: true, args: ['--use-gl=angle','--enable-unsafe-swiftshader'] });
const p = await b.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const errs = [];
p.on('console', m => m.type()==='error' && errs.push(m.text()));
p.on('pageerror', e => errs.push('PAGEERR '+e.message));
await p.goto('http://localhost:4173/', { waitUntil: 'networkidle', timeout: 40000 });
await p.waitForTimeout(3000);
const probe = await p.evaluate(() => ({
  scrubber: !!document.querySelector('.fr-scrubber'),
  ticks: document.querySelectorAll('.fr-tick').length,
  date: document.querySelector('.fr-date')?.textContent,
  live: document.querySelector('.fr-livebtn')?.className,
}));
await p.screenshot({ path: '/tmp/fr_live.png' });
// scrub back: set range to ~70% then a flag-collapse area
const range = await p.$('.fr-range');
const max = await p.evaluate(el => +el.max, range);
const target = Math.round(max * 0.78);
await p.evaluate(({el,v}) => { const set=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set; set.call(el,v); el.dispatchEvent(new Event('input',{bubbles:true})); }, {el: range, v: String(target)});
await p.waitForTimeout(1500);
const scrubDate = await p.evaluate(() => document.querySelector('.fr-date')?.textContent);
await p.screenshot({ path: '/tmp/fr_scrub.png' });
console.log(JSON.stringify({ probe, scrubDate, errs: errs.slice(0,5) }, null, 0));
await b.close();
