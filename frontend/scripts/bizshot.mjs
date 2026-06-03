import { chromium } from 'playwright';
const b = await chromium.launch({ channel:'chrome', headless:true, args:['--use-gl=angle','--enable-unsafe-swiftshader'] });
const p = await b.newPage({ viewport:{width:1440,height:900}, deviceScaleFactor:2 });
const errs=[]; p.on('console',m=>m.type()==='error'&&errs.push(m.text())); p.on('pageerror',e=>errs.push('PE '+e.message));
await p.goto('http://localhost:4173/', { waitUntil:'networkidle', timeout:40000 });
await p.waitForTimeout(3000);
await p.click('.fr-row'); // expand top critical (Shanghai)
await p.waitForTimeout(2500);
await (await p.$('.fr-feed')).screenshot({ path:'/tmp/fr_biz.png' });
console.log(JSON.stringify({errs:errs.slice(0,4)}));
await b.close();
