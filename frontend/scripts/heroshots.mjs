import { chromium } from 'playwright';
const OUT = '/Users/joshspadaro/dev/freight-radar/docs';
const b = await chromium.launch({ channel:'chrome', headless:true, args:['--use-gl=angle','--enable-unsafe-swiftshader'] });
const p = await b.newPage({ viewport:{width:1440,height:860}, deviceScaleFactor:2 });
await p.goto('http://localhost:4173/', { waitUntil:'networkidle', timeout:40000 });
await p.waitForTimeout(4500);
await p.screenshot({ path:`${OUT}/hero.png` });
await p.click('.fr-row');                 // top critical -> fly-to + brief
await p.waitForTimeout(3500);
await p.screenshot({ path:`${OUT}/flag-detail.png` });
await p.click('.fr-livebtn');             // back to live
await p.waitForTimeout(700);
const range = await p.$('.fr-range');
const max = await p.evaluate(el=>+el.max, range);
await p.evaluate(({el,v})=>{const s=Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype,'value').set;s.call(el,v);el.dispatchEvent(new Event('input',{bubbles:true}));},{el:range,v:String(Math.round(max*0.8))});
await p.waitForTimeout(1500);
await p.screenshot({ path:`${OUT}/timescrubber.png` });
console.log('hero images regenerated');
await b.close();
