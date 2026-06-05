// Client-side routing — a faithful mirror of backend/freight_radar/business/
// exposure.py (route maps) + port_resolver.py (resolve + derive_region), so an
// uploaded CSV recomputes exposure in the browser with the SAME logic as the
// pipeline. A parity test (scripts/check_exposure_parity.mjs) guards against drift:
// the JS result on the sample CSV must match the Python-generated exposure.json.

// A raw row from ports_lookup.json: a column-name header plus value rows.
export interface PortLookup {
  cols: string[];
  rows: (string | number | null)[][];
}

// A resolved port record (the columns this resolver cares about).
export interface PortRecord {
  portid: string | number | null;
  name: string | number | null;
  locode: string | number | null;
  continent: string | number | null;
  lat: number | null;
  lon: number | null;
}

// What resolve() identified a token against, or null if unmatched.
export type MatchKind = 'portid' | 'locode' | 'name' | null;

// The minimal lane shape routeLane reads (a faithful subset of CsvLane).
export interface RouteLaneInput {
  origin_region?: string | null;
  dest_region?: string | null;
  origin_port?: string | null;
  dest_port?: string | null;
}

export interface Resolver {
  resolve: (token: string | number | null | undefined) => [PortRecord | null, MatchKind];
  regionFor: (
    token: string | number | null | undefined,
    given: string | null | undefined
  ) => [string | null, PortRecord | null, MatchKind];
}

export interface RouteDetail {
  origin_portid: string | number | null;
  dest_portid: string | number | null;
  origin_region: string | null;
  dest_region: string | null;
  matched_by: Exclude<MatchKind, null>[];
  routing_confidence: string;
}

export interface RouteResult {
  cps: Set<string>;
  detail: RouteDetail;
}

// --- routing model (mirror of exposure.py) ---------------------------------
export const GATEWAY: Record<string, string[]> = {
  'Black Sea': ['Bosporus Strait'],
  Baltic: ['Oresund Strait'],
  Gulf: ['Strait of Hormuz'],
};
export const PORT_CHOKEPOINTS: Record<string, string[]> = { 'Rostov-on-Don': ['Kerch Strait'] };

// corridor keyed by the two regions sorted + joined (order-independent, like frozenset)
const CORRIDOR_RAW: [string[], string[]][] = [
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
const CORRIDOR = new Map<string, string[]>(
  CORRIDOR_RAW.map(([pair, cps]): [string, string[]] => [[...pair].sort().join('|'), cps])
);

export const REROUTE_DELAY: Record<string, number> = {
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
const normLocode = (s: string | number | null | undefined) =>
  String(s || '')
    .toUpperCase()
    .replace(/[^A-Z0-9]/g, '');
const normName = (s: string | number | null | undefined) =>
  String(s || '')
    .toLowerCase()
    .replace(/[^a-z0-9]/g, '');

export function deriveRegion(
  continent: string | number | null | undefined,
  lat: number | null | undefined,
  lon: number | null | undefined
): string | null {
  if (lat == null || lon == null) return null;
  const c = String(continent || '');
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

export function makeResolver(lookup: PortLookup | null | undefined): Resolver {
  const cols = lookup?.cols || [];
  const idx: Record<string, number> = Object.fromEntries(cols.map((c, i) => [c, i]));
  const byId = new Map<string | number | null, PortRecord>(),
    byLoc = new Map<string, PortRecord>(),
    byName = new Map<string, PortRecord>();
  for (const r of lookup?.rows || []) {
    const rec: PortRecord = {
      portid: r[idx.portid],
      name: r[idx.name],
      locode: r[idx.locode],
      continent: r[idx.continent],
      lat: r[idx.lat] as number | null,
      lon: r[idx.lon] as number | null,
    };
    byId.set(rec.portid, rec);
    if (rec.locode) {
      const k = normLocode(rec.locode);
      if (!byLoc.has(k)) byLoc.set(k, rec);
    }
    const n = normName(rec.name);
    if (n && !byName.has(n)) byName.set(n, rec);
  }
  const resolve = (token: string | number | null | undefined): [PortRecord | null, MatchKind] => {
    if (!token) return [null, null];
    const existing = byId.get(token);
    if (existing) return [existing, 'portid'];
    const lc = normLocode(token);
    const byLocRec = byLoc.get(lc);
    if (byLocRec) return [byLocRec, 'locode'];
    const nm = normName(token);
    const byNameRec = byName.get(nm);
    if (byNameRec) return [byNameRec, 'name'];
    return [null, null];
  };
  const regionFor = (
    token: string | number | null | undefined,
    given: string | null | undefined
  ): [string | null, PortRecord | null, MatchKind] => {
    const [rec, matched] = resolve(token);
    if (given && given.trim()) return [given.trim(), rec, matched];
    if (rec) return [deriveRegion(rec.continent, rec.lat, rec.lon), rec, matched];
    return [null, null, null];
  };
  return { resolve, regionFor };
}

// --- route a lane (mirror of exposure.route_lane) --------------------------
export function routeLane(
  lane: RouteLaneInput,
  resolver: Resolver | null | undefined
): RouteResult {
  let oRegion: string | null = (lane.origin_region || '').trim();
  let dRegion: string | null = (lane.dest_region || '').trim();
  let oRec: PortRecord | null = null,
    dRec: PortRecord | null = null,
    oMatch: MatchKind = null,
    dMatch: MatchKind = null,
    regionDerived: string | null | boolean = false;
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
  const cps = new Set<string>();
  for (const region of [oRegion, dRegion]) (GATEWAY[region ?? ''] || []).forEach((x) => cps.add(x));
  for (const port of [lane.origin_port, lane.dest_port])
    (PORT_CHOKEPOINTS[port ?? ''] || []).forEach((x) => cps.add(x));
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
      matched_by: [oMatch, dMatch].filter((m): m is Exclude<MatchKind, null> => Boolean(m)),
      routing_confidence: conf,
    },
  };
}
