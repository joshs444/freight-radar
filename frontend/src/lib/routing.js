// Client-side routing — a faithful mirror of backend/freight_radar/business/
// exposure.py (route maps) + port_resolver.py (resolve + derive_region), so an
// uploaded CSV recomputes exposure in the browser with the SAME logic as the
// pipeline. A parity test (scripts/check_exposure_parity.mjs) guards against drift:
// the JS result on the sample CSV must match the Python-generated exposure.json.

// --- routing model (mirror of exposure.py) ---------------------------------
export const GATEWAY = {
  'Black Sea': ['Bosporus Strait'],
  Baltic: ['Oresund Strait'],
  Gulf: ['Strait of Hormuz'],
};
export const PORT_CHOKEPOINTS = { 'Rostov-on-Don': ['Kerch Strait'] };

// corridor keyed by the two regions sorted + joined (order-independent, like frozenset)
const CORRIDOR_RAW = [
  [
    ['East Asia', 'North Europe'],
    ['Malacca Strait', 'Bab el-Mandeb Strait', 'Suez Canal', 'Gibraltar Strait', 'Dover Strait'],
  ],
  [
    ['Southeast Asia', 'North Europe'],
    ['Malacca Strait', 'Bab el-Mandeb Strait', 'Suez Canal', 'Gibraltar Strait', 'Dover Strait'],
  ],
  [
    ['South Asia', 'North Europe'],
    ['Bab el-Mandeb Strait', 'Suez Canal', 'Gibraltar Strait', 'Dover Strait'],
  ],
  [
    ['East Asia', 'Mediterranean'],
    ['Malacca Strait', 'Bab el-Mandeb Strait', 'Suez Canal'],
  ],
  [
    ['Southeast Asia', 'Mediterranean'],
    ['Malacca Strait', 'Bab el-Mandeb Strait', 'Suez Canal'],
  ],
  [['East Asia', 'North America East'], ['Panama Canal']],
  [['Southeast Asia', 'North America East'], ['Panama Canal']],
  [['East Asia', 'North America West'], ['Taiwan Strait']],
  [['Gulf', 'East Asia'], ['Malacca Strait']],
  [
    ['Gulf', 'North Europe'],
    ['Bab el-Mandeb Strait', 'Suez Canal', 'Gibraltar Strait', 'Dover Strait'],
  ],
  [
    ['Gulf', 'Mediterranean'],
    ['Bab el-Mandeb Strait', 'Suez Canal'],
  ],
  [
    ['Black Sea', 'North Europe'],
    ['Gibraltar Strait', 'Dover Strait'],
  ],
  [['Mediterranean', 'North America East'], ['Gibraltar Strait']],
];
const CORRIDOR = new Map(CORRIDOR_RAW.map(([pair, cps]) => [[...pair].sort().join('|'), cps]));

export const REROUTE_DELAY = {
  'Suez Canal': 12,
  'Bab el-Mandeb Strait': 12,
  'Cape of Good Hope': 10,
  'Strait of Hormuz': 6,
  'Panama Canal': 8,
  'Malacca Strait': 3,
  'Bosporus Strait': 4,
  'Kerch Strait': 4,
  'Oresund Strait': 2,
  'Gibraltar Strait': 3,
  'Dover Strait': 2,
  'Taiwan Strait': 3,
  'Korea Strait': 2,
};
export const DEFAULT_CHOKE_DELAY = 3;

// --- resolver (mirror of port_resolver.py) ---------------------------------
const normLocode = (s) =>
  String(s || '')
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '');
const normName = (s) =>
  String(s || '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '');

export function deriveRegion(continent, lat, lon) {
  if (lat == null || lon == null) return null;
  const c = continent || '';
  if (c.includes('Asia')) {
    if (lon >= 45 && lon <= 60 && lat >= 20 && lat <= 32) return 'Gulf';
    if (lon >= 118 && lat >= 18) return 'East Asia';
    if (lon >= 95 && lon < 118 && lat < 20) return 'Southeast Asia';
    if (lon >= 60 && lon < 95) return 'South Asia';
    if (lon >= 118) return 'East Asia';
    return 'Southeast Asia';
  }
  if (c.includes('Europe')) {
    if (lat >= 51 && lon >= -10 && lon <= 15) return 'North Europe';
    if (lat >= 27 && lat <= 47 && lon >= -6 && lon <= 37) return 'Mediterranean';
    if (lat >= 53 && lon > 15) return 'Baltic';
    if (lat >= 40 && lat <= 48 && lon >= 27 && lon <= 42) return 'Black Sea';
    return 'North Europe';
  }
  if (c.includes('North America')) return lon <= -100 ? 'North America West' : 'North America East';
  return null;
}

export function makeResolver(lookup) {
  const cols = lookup?.cols || [];
  const idx = Object.fromEntries(cols.map((c, i) => [c, i]));
  const byId = new Map(),
    byLoc = new Map(),
    byName = new Map();
  for (const r of lookup?.rows || []) {
    const rec = {
      portid: r[idx.portid],
      name: r[idx.name],
      locode: r[idx.locode],
      continent: r[idx.continent],
      lat: r[idx.lat],
      lon: r[idx.lon],
    };
    byId.set(rec.portid, rec);
    if (rec.locode) {
      const k = normLocode(rec.locode);
      if (!byLoc.has(k)) byLoc.set(k, rec);
    }
    const n = normName(rec.name);
    if (n && !byName.has(n)) byName.set(n, rec);
  }
  const resolve = (token) => {
    if (!token) return [null, null];
    if (byId.has(token)) return [byId.get(token), 'portid'];
    const lc = normLocode(token);
    if (byLoc.has(lc)) return [byLoc.get(lc), 'locode'];
    const nm = normName(token);
    if (byName.has(nm)) return [byName.get(nm), 'name'];
    return [null, null];
  };
  const regionFor = (token, given) => {
    const [rec, matched] = resolve(token);
    if (given && given.trim()) return [given.trim(), rec, matched];
    if (rec) return [deriveRegion(rec.continent, rec.lat, rec.lon), rec, matched];
    return [null, null, null];
  };
  return { resolve, regionFor };
}

// --- route a lane (mirror of exposure.route_lane) --------------------------
export function routeLane(lane, resolver) {
  let oRegion = (lane.origin_region || '').trim();
  let dRegion = (lane.dest_region || '').trim();
  let oRec = null,
    dRec = null,
    oMatch = null,
    dMatch = null,
    regionDerived = false;
  if (resolver) {
    const [or, orec, om] = resolver.regionFor(lane.origin_port || '', oRegion);
    const [dr, drec, dm] = resolver.regionFor(lane.dest_port || '', dRegion);
    regionDerived = (!oRegion && or) || (!dRegion && dr);
    oRegion = or;
    dRegion = dr;
    oRec = orec;
    dRec = drec;
    oMatch = om;
    dMatch = dm;
  }
  const cps = new Set();
  for (const region of [oRegion, dRegion]) (GATEWAY[region] || []).forEach((x) => cps.add(x));
  for (const port of [lane.origin_port, lane.dest_port])
    (PORT_CHOKEPOINTS[port] || []).forEach((x) => cps.add(x));
  const key = [oRegion, dRegion].filter(Boolean).sort().join('|');
  (CORRIDOR.get(key) || []).forEach((x) => cps.add(x));

  const bothResolved = resolver ? oRec && dRec : true;
  let conf = 'none';
  if (cps.size && bothResolved && !regionDerived) conf = 'high';
  else if (cps.size && bothResolved) conf = 'medium';
  else if (cps.size) conf = 'low';

  return {
    cps,
    detail: {
      origin_portid: oRec?.portid || null,
      dest_portid: dRec?.portid || null,
      origin_region: oRegion,
      dest_region: dRegion,
      matched_by: [oMatch, dMatch].filter(Boolean),
      routing_confidence: conf,
    },
  };
}
