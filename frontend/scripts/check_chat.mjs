// Honesty test for the Tier-1 chat: load the REAL published sidecars, run the
// engine over a battery of questions, and assert that every fact each answer cites
// genuinely exists in the sidecar it claims. If the engine ever states a number it
// can't trace to source, this fails. Run: `node scripts/check_chat.mjs`.

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { ask, buildIndex, SUGGESTED } from '../src/lib/ask.js';

const here = dirname(fileURLToPath(import.meta.url));
const dataDir = join(here, '..', 'public', 'data');
const load = (f) => { try { return JSON.parse(readFileSync(join(dataDir, f), 'utf8')); } catch { return null; } };

const data = {
  snapshot: load('snapshot.json'), flags: load('flags.json'), lanes: load('lanes.json'),
  timeseries: load('timeseries.json'), exposure: load('exposure.json'), news: load('news.json'),
  market: load('market.json'), stress: load('stress.json'), brief: load('brief.json'), events: load('events.json'),
  world: load('world.json'),
};

// raw text of each sidecar — a grounded fact's value must appear verbatim here
const RAW = Object.fromEntries(Object.keys(data).map((k) => [`${k}.json`, JSON.stringify(data[k] ?? {})]));

const QUESTIONS = [
  ...SUGGESTED,
  'whats going on here', 'how is the strait of hormuz', 'tell me about shanghai',
  'what is the biggest risk', 'what is improving', 'what is getting worse',
  'am i exposed to hormuz', 'am i exposed to suez', 'what changed this week',
  'why is brent up', 'list all disruptions', 'how many chokepoints are disrupted',
  'how is the taiwan strait', 'tell me about kerch strait', 'what about panama',
  'how many ships are out today', 'how many port calls', 'how much cargo was delivered',
  'how busy is global freight', 'how many vessels in transit',
  'hello', 'something totally unrelated to freight',
];

const index = buildIndex(data);
let checks = 0, fails = 0;
const grounded = (v, src) => {
  // a fact is grounded if its raw value string appears in the cited sidecar
  const needle = typeof v === 'number' ? String(v) : JSON.stringify(v);
  return RAW[src] != null && RAW[src].includes(needle);
};

for (const q of QUESTIONS) {
  const a = ask(q, data, index);
  if (!a) { console.error(`✗ "${q}" → null answer`); fails++; continue; }
  // help/greeting answers legitimately carry no facts
  for (const f of a.facts || []) {
    checks++;
    if (!a.cites.includes(f.src)) { console.error(`✗ "${q}" cites missing ${f.src}`); fails++; continue; }
    if (!grounded(f.v, f.src)) {
      console.error(`✗ "${q}" UNGROUNDED fact ${JSON.stringify(f.v)} not found in ${f.src}`);
      fails++;
    }
  }
  // every answer with facts must cite at least one sidecar
  if ((a.facts || []).length > 0 && a.cites.length === 0) {
    console.error(`✗ "${q}" has facts but no cites`); fails++;
  }
}

console.log(`chat grounding: ${checks} facts checked across ${QUESTIONS.length} questions, ${fails} failures`);
if (fails > 0) { process.exit(1); }
console.log('✓ every cited fact traces to its source sidecar');
