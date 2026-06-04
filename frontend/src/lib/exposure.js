// Client-side exposure — a faithful mirror of backend/freight_radar/business/
// exposure.py (cost-of-disruption stack). Recomputes a user's exposure entirely in
// the browser from an uploaded CSV. Parity with the Python pipeline is enforced by
// scripts/check_exposure_parity.mjs.

import { routeLane, REROUTE_DELAY, DEFAULT_CHOKE_DELAY } from './routing.js';

const CARRYING_RATE = [0.20, 0.25, 0.30];
const REROUTE_PREMIUM_PER_TEU_DAY = [15, 25, 40];
const KEYS = ['low', 'expected', 'high'];

// Python round() is round-half-to-even; mirror it so the bands match exactly.
function pyRound(x) {
  const f = Math.floor(x);
  const d = x - f;
  if (d < 0.5) return f;
  if (d > 0.5) return f + 1;
  return f % 2 === 0 ? f : f + 1;
}

const isChokepoint = (flag) => (flag.kind || '').startsWith('chokepoint') || flag.kind === 'cape_reroute';

function delayDays(flag) {
  if (isChokepoint(flag)) return REROUTE_DELAY[flag.entity] ?? DEFAULT_CHOKE_DELAY;
  return Math.max(2, pyRound((flag.severity ?? 30) / 12));
}

function delayBand(flag) {
  const d = delayDays(flag);
  return { low: Math.max(1, pyRound(d * 0.7)), expected: d, high: pyRound(d * 1.35) };
}

const carryingBand = (value, db) =>
  Object.fromEntries(KEYS.map((k, i) => [k, pyRound((value * CARRYING_RATE[i] * db[k]) / 365)]));
const workingCapitalBand = (value, db) =>
  Object.fromEntries(KEYS.map((k) => [k, pyRound((value * db[k]) / 365)]));
function rerouteBand(teu, flag, db) {
  if (!isChokepoint(flag) || REROUTE_DELAY[flag.entity] == null) return { low: 0, expected: 0, high: 0 };
  return Object.fromEntries(KEYS.map((k, i) => [k, pyRound(teu * REROUTE_PREMIUM_PER_TEU_DAY[i] * db[k])]));
}
const sumBand = (...bands) => Object.fromEntries(KEYS.map((k) => [k, pyRound(bands.reduce((s, b) => s + (b[k] || 0), 0))]));

function prepareRoutes(lanes, resolver) {
  for (const ln of lanes) {
    const { cps, detail } = routeLane(ln, resolver);
    ln._route_cps = cps;
    ln._routing = detail;
    ln._origin_portid = detail.origin_portid;
    ln._dest_portid = detail.dest_portid;
  }
}

function exposedLanes(flag, lanes) {
  if (isChokepoint(flag)) return lanes.filter((ln) => ln._route_cps.has(flag.entity));
  return lanes.filter((ln) =>
    flag.portid === ln._origin_portid || flag.portid === ln._dest_portid
    || flag.entity === ln.origin_port || flag.entity === ln.dest_port);
}

const ORDER = { high: 3, medium: 2, low: 1, none: 0 };

function businessForFlag(flag, lanes) {
  const ls = exposedLanes(flag, lanes);
  const value = ls.reduce((s, ln) => s + ln.annual_value_usd, 0);
  const teu = ls.reduce((s, ln) => s + ln.annual_teu, 0);
  const db = delayBand(flag);
  const byItem = {};
  ls.forEach((ln) => { byItem[ln.item_category] = (byItem[ln.item_category] || 0) + ln.annual_value_usd; });
  const topItems = Object.entries(byItem).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([k]) => k);

  const carrying = carryingBand(value, db);
  const reroute = rerouteBand(teu, flag, db);
  const wc = workingCapitalBand(value, db);
  const total = sumBand(carrying, reroute);
  const bestConf = ls.reduce((best, ln) => {
    const c = ln._routing?.routing_confidence || 'none';
    return ORDER[c] > ORDER[best] ? c : best;
  }, 'none');

  const method = [{ line: 'carrying_cost_of_delay', basis: `value × ${Math.round(CARRYING_RATE[1] * 100)}%/yr carrying × delay/365` }];
  if (reroute.expected) method.push({ line: 'reroute_premium', basis: `TEU × ~$${REROUTE_PREMIUM_PER_TEU_DAY[1]}/TEU/diversion-day × delay` });
  method.push({ line: 'working_capital_tied_up', basis: 'value × delay/365 (balance-sheet, excluded from P&L total)' });

  return {
    exposed_value_usd: pyRound(value),
    exposed_teu: pyRound(teu),
    exposed_lanes: ls.slice().sort((a, b) => b.annual_value_usd - a.annual_value_usd).map((ln) => ({
      lane_id: ln.lane_id, from: ln.origin_port, to: ln.dest_port, item: ln.item_category,
      value_usd: pyRound(ln.annual_value_usd), routing_confidence: ln._routing?.routing_confidence || 'none',
    })),
    lane_count: ls.length,
    top_items: topItems,
    routing_confidence: bestConf,
    est_delay_days: db,
    cost_stack: {
      carrying_cost_of_delay_usd: carrying,
      reroute_premium_usd: reroute,
      total_cost_of_disruption_usd: total,
      working_capital_tied_up_usd: wc,
    },
    method,
    carrying_cost_of_delay_usd: carrying,
    working_capital_tied_up_usd: wc,
    total_cost_of_disruption_usd: total,
    carrying_rate_assumed: CARRYING_RATE[1],
  };
}

// Recompute exposure for a user's lanes. Returns { flags (with .business), summary }.
export function computeExposure(flags, lanes, resolver) {
  prepareRoutes(lanes, resolver);
  const out = flags.map((f) => ({ ...f, business: businessForFlag(f, lanes) }));
  const active = out.filter((f) => f.lifecycle !== 'resolved');
  const carry = { low: 0, expected: 0, high: 0 };
  const wc = { low: 0, expected: 0, high: 0 };
  const total = { low: 0, expected: 0, high: 0 };
  const exposedLaneIds = new Set();
  let disrupted = 0;
  for (const f of active) {
    const b = f.business;
    if (b.lane_count) {
      disrupted += 1;
      KEYS.forEach((k) => {
        carry[k] += b.carrying_cost_of_delay_usd[k];
        wc[k] += b.working_capital_tied_up_usd[k];
        total[k] += b.total_cost_of_disruption_usd[k];
      });
      b.exposed_lanes.forEach((ln) => exposedLaneIds.add(ln.lane_id));
    }
  }
  const totalValue = lanes.reduce((s, ln) => s + ln.annual_value_usd, 0);
  const exposedValue = lanes.filter((ln) => exposedLaneIds.has(ln.lane_id)).reduce((s, ln) => s + ln.annual_value_usd, 0);
  const modeled = lanes.filter((ln) => ln._route_cps.size).length;
  const summary = {
    total_flows: lanes.length,
    total_value_usd: pyRound(totalValue),
    exposed_lanes: exposedLaneIds.size,
    exposed_value_usd: pyRound(exposedValue),
    carrying_cost_of_delay_usd: { low: pyRound(carry.low), expected: pyRound(carry.expected), high: pyRound(carry.high) },
    working_capital_tied_up_usd: { low: pyRound(wc.low), expected: pyRound(wc.expected), high: pyRound(wc.high) },
    total_cost_of_disruption_usd: { low: pyRound(total.low), expected: pyRound(total.expected), high: pyRound(total.high) },
    carrying_rate_assumed: CARRYING_RATE[1],
    active_disruptions_hitting_you: disrupted,
    lanes_with_known_route: modeled,
    coverage_pct: lanes.length ? Math.round((modeled / lanes.length) * 1000) / 10 : 0,
  };
  return { flags: out, summary };
}
