// Parity gate for the client-side exposure port: run the JS exposure engine on the
// SAME sample trade CSV the Python pipeline uses, and assert the portfolio summary +
// per-flag cost stacks match the Python-generated exposure.json / flags.json. If the
// JS mirror ever drifts from backend/freight_radar/business/exposure.py, this fails.
//   node scripts/check_exposure_parity.mjs

import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { computeExposure } from '../src/lib/exposure.js';
import { makeResolver } from '../src/lib/routing.js';
import { parseCSV } from '../src/lib/csv.js';

const here = dirname(fileURLToPath(import.meta.url));
const dataDir = join(here, '..', 'public', 'data');
const root = join(here, '..', '..');
const load = (p) => JSON.parse(readFileSync(p, 'utf8'));

const lookup = load(join(dataDir, 'ports_lookup.json'));
const flags = load(join(dataDir, 'flags.json'));
const pyExposure = load(join(dataDir, 'exposure.json'));

// the pipeline's exact input CSV (same file the backend resolver reads)
const csvText = readFileSync(join(root, 'backend', 'samples', 'business_flows.csv'), 'utf8');
const objs = parseCSV(csvText);
const lanes = objs.map((o, i) => ({
  lane_id: o.lane_id || `L${i + 1}`,
  origin_region: o.origin_region || '', dest_region: o.dest_region || '',
  origin_port: o.origin_port || '', dest_port: o.dest_port || '',
  item_category: o.item_category || 'Goods',
  annual_value_usd: parseFloat(o.annual_value_usd || 0), annual_teu: parseFloat(o.annual_teu || 0),
}));

const resolver = makeResolver(lookup);
const flagsForCalc = flags.map((f) => ({ ...f }));
const { flags: jsFlags, summary } = computeExposure(flagsForCalc, lanes, resolver);

let fails = 0;
const TOL = 2; // ±$2 tolerance for float-rounding edge cases
const near = (a, b) => Math.abs((a || 0) - (b || 0)) <= TOL;
const checkBand = (label, js, py) => {
  for (const k of ['low', 'expected', 'high']) {
    if (!near(js?.[k], py?.[k])) { console.error(`✗ ${label}.${k}: js=${js?.[k]} py=${py?.[k]}`); fails++; }
  }
};

// portfolio summary parity
checkBand('summary.carrying', summary.carrying_cost_of_delay_usd, pyExposure.carrying_cost_of_delay_usd);
checkBand('summary.total', summary.total_cost_of_disruption_usd, pyExposure.total_cost_of_disruption_usd);
checkBand('summary.working_capital', summary.working_capital_tied_up_usd, pyExposure.working_capital_tied_up_usd);
if (!near(summary.exposed_value_usd, pyExposure.exposed_value_usd)) {
  console.error(`✗ exposed_value: js=${summary.exposed_value_usd} py=${pyExposure.exposed_value_usd}`); fails++;
}
if (summary.lanes_with_known_route !== pyExposure.lanes_with_known_route) {
  console.error(`✗ coverage: js=${summary.lanes_with_known_route} py=${pyExposure.lanes_with_known_route}`); fails++;
}
if (summary.active_disruptions_hitting_you !== pyExposure.active_disruptions_hitting_you) {
  console.error(`✗ disruptions: js=${summary.active_disruptions_hitting_you} py=${pyExposure.active_disruptions_hitting_you}`); fails++;
}

// per-flag cost-stack parity
for (const jf of jsFlags) {
  const pf = flags.find((x) => x.flag_id === jf.flag_id);
  if (!pf?.business) continue;
  if (jf.business.lane_count !== pf.business.lane_count) {
    console.error(`✗ ${pf.entity} lane_count: js=${jf.business.lane_count} py=${pf.business.lane_count}`); fails++;
  }
  checkBand(`${pf.entity}.total`, jf.business.total_cost_of_disruption_usd, pf.business.total_cost_of_disruption_usd);
  checkBand(`${pf.entity}.reroute`, jf.business.cost_stack.reroute_premium_usd, pf.business.cost_stack.reroute_premium_usd);
}

console.log(`exposure parity: summary + ${jsFlags.length} flags checked, ${fails} mismatches`);
if (fails) process.exit(1);
console.log('✓ JS exposure matches the Python pipeline on the sample CSV');
