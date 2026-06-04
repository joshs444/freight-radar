// Headless verification of the narrative layer: stress gauge + brief card render,
// and the chat actually answers a question with a citation. Screenshots both.
//   node scripts/verify_narrative.mjs <url>
import { chromium } from 'playwright';

const url = process.argv[2] || 'http://localhost:4173/';
const browser = await chromium.launch({
  channel: 'chrome', headless: true,
  args: ['--use-gl=angle', '--ignore-gpu-blocklist', '--enable-unsafe-swiftshader', '--enable-webgl'],
});
const page = await browser.newPage({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2 });
const errors = [];
page.on('console', (m) => m.type() === 'error' && errors.push(m.text()));
page.on('pageerror', (e) => errors.push('PAGEERROR: ' + e.message));

await page.goto(url, { waitUntil: 'networkidle', timeout: 45000 });
await page.waitForTimeout(5000);

const base = await page.evaluate(() => ({
  stressNum: document.querySelector('.fr-stress-num')?.textContent?.trim(),
  stressBadge: document.querySelector('.fr-stress-badge')?.textContent?.trim(),
  briefHeadline: document.querySelector('.fr-brief-headline')?.textContent?.trim(),
  briefBullets: document.querySelectorAll('.fr-brief-li').length,
  fab: !!document.querySelector('.fr-chat-fab'),
  worldTiles: document.querySelectorAll('.fr-w-tile').length,
  worldFirst: document.querySelector('.fr-w-tile .fr-w-val')?.textContent?.trim(),
  worldTrends: document.querySelectorAll('.fr-w-trend').length,
}));
await page.screenshot({ path: '/tmp/fr_narrative.png' });

// open the chat and ask a question
await page.click('.fr-chat-fab');
await page.waitForTimeout(400);
await page.click('.fr-chat-starter .fr-chat-chip:nth-child(1)'); // first suggested
await page.waitForTimeout(500);
const chat = await page.evaluate(() => {
  const bots = [...document.querySelectorAll('.fr-chat-msg.bot')];
  const last = bots[bots.length - 1];
  return {
    botReplies: bots.length,
    lastText: last?.querySelector('.fr-chat-line')?.textContent?.trim()?.slice(0, 90),
    cites: [...(last?.querySelectorAll('.fr-chat-cite') || [])].map((c) => c.textContent),
  };
});
// also type a free-text question
await page.fill('.fr-chat-input input', 'how is the strait of hormuz');
await page.press('.fr-chat-input input', 'Enter');
await page.waitForTimeout(500);
const chat2 = await page.evaluate(() => {
  const bots = [...document.querySelectorAll('.fr-chat-msg.bot')];
  const last = bots[bots.length - 1];
  return { lastText: last?.textContent?.trim()?.slice(0, 120), cites: [...(last?.querySelectorAll('.fr-chat-cite') || [])].map((c) => c.textContent) };
});
await page.screenshot({ path: '/tmp/fr_chat.png' });

console.log(JSON.stringify({ base, chat, chat2, errors }, null, 2));
await browser.close();
if (errors.length) process.exit(2);
if (!base.stressNum || !base.briefHeadline || base.briefBullets === 0) process.exit(3);
if (chat.botReplies === 0 || chat.cites.length === 0) process.exit(4);
