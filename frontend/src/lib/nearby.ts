import type { AppData } from '../types.ts';
import { gdacsReportUrl } from './sources.ts';

// The P6 "Nearby" surface, client-side. For a selected SPINE entity (a port/chokepoint),
// gather the CITED CONTEXT items already loaded in the browser that sit within a radius,
// ordered ONLY by distance. This is the anti-centrum primitive: co-location is association,
// never a stated cause, never a severity ranking, never a base-rate. It mirrors the backend
// store.nearby() semantics exactly (same sources, same distance-only order, same disclaimer)
// so the human panel and the agent/MCP surface tell the identical story.

export const ASSOCIATION_ONLY =
  'Co-located in space/time — association only, never a stated cause.';

export interface NearbyItem {
  layer: string;
  label: string; // the context family ("USGS earthquake", "sea state", …)
  km: number;
  place: string | null;
  detail: string | null; // a short cited value, shown as-is (never a computed score)
  url: string | null;
  source: string | null;
}

interface GeoPoint {
  lat?: number | null;
  lon?: number | null;
  [k: string]: unknown;
}

function haversineKm(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const r = 6371;
  const p1 = (lat1 * Math.PI) / 180;
  const p2 = (lat2 * Math.PI) / 180;
  const dp = ((lat2 - lat1) * Math.PI) / 180;
  const dl = ((lon2 - lon1) * Math.PI) / 180;
  const a = Math.sin(dp / 2) ** 2 + Math.cos(p1) * Math.cos(p2) * Math.sin(dl / 2) ** 2;
  return 2 * r * Math.asin(Math.sqrt(a));
}

const PLACE_KEYS = ['place', 'name', 'port', 'title', 'river'] as const;
const placeOf = (it: GeoPoint): string | null => {
  for (const k of PLACE_KEYS) {
    const v = it[k];
    if (typeof v === 'string' && v) return v;
  }
  return null;
};

// per-layer: where the items live in AppData, the family label, and a cited-value formatter
interface Source {
  layer: string;
  label: string;
  items: (d: AppData) => GeoPoint[] | undefined;
  source: (d: AppData) => string | null;
  detail: (it: GeoPoint) => string | null;
  url?: (it: GeoPoint) => string | null;
}

const num = (v: unknown): number | null => (typeof v === 'number' ? v : null);
const str = (v: unknown): string | null => (typeof v === 'string' ? v : null);

const SOURCES: Source[] = [
  {
    layer: 'quakes',
    label: 'USGS earthquake',
    items: (d) => d.quakes?.items as GeoPoint[] | undefined,
    source: (d) => d.quakes?.source ?? 'USGS',
    detail: (it) => (num(it.mag) != null ? `M${(num(it.mag) as number).toFixed(1)}` : null),
    url: (it) => str(it.url),
  },
  {
    layer: 'news_geo',
    label: 'GDELT news',
    items: (d) => d.newsGeo?.items as GeoPoint[] | undefined,
    source: (d) => d.newsGeo?.source ?? 'GDELT',
    detail: (it) => str(it.category_label) ?? str(it.domain),
    url: (it) => str(it.url),
  },
  {
    layer: 'eonet',
    label: 'NASA natural event',
    items: (d) => d.eonet?.items as GeoPoint[] | undefined,
    source: (d) => d.eonet?.source ?? 'NASA EONET',
    detail: (it) => str(it.category),
    url: (it) => str(it.url),
  },
  {
    layer: 'marine',
    label: 'sea state',
    items: (d) => d.marine?.items as GeoPoint[] | undefined,
    source: (d) => d.marine?.source ?? 'Open-Meteo',
    detail: (it) =>
      num(it.wave_height_m) != null
        ? `${(num(it.wave_height_m) as number).toFixed(1)} m wave`
        : null,
    url: () => null,
  },
  {
    layer: 'tides',
    label: 'water level',
    items: (d) => d.tides?.items as GeoPoint[] | undefined,
    source: (d) => d.tides?.source ?? 'NOAA CO-OPS',
    detail: (it) =>
      num(it.water_level_ft) != null ? `${(num(it.water_level_ft) as number).toFixed(1)} ft` : null,
    url: (it) => str(it.url),
  },
  {
    layer: 'streamflow',
    label: 'river stage',
    items: (d) => d.streamflow?.items as GeoPoint[] | undefined,
    source: (d) => d.streamflow?.source ?? 'USGS',
    detail: (it) =>
      num(it.stage_ft) != null ? `${(num(it.stage_ft) as number).toFixed(1)} ft stage` : null,
    url: (it) => str(it.url),
  },
  {
    layer: 'disruptions',
    label: 'GDACS hazard alert',
    items: (d) => d.disruptions?.events as GeoPoint[] | undefined,
    source: (d) => d.disruptions?.source ?? 'GDACS',
    detail: (it) => {
      const lvl = str(it.alertlevel);
      const ty = str(it.type_label);
      return [lvl && `${lvl} alert`, ty].filter(Boolean).join(' · ') || null;
    },
    url: (it) =>
      str(it.eventid) || num(it.eventid) != null
        ? gdacsReportUrl(str(it.type) ?? '', it.eventid as number | string)
        : null,
  },
];

// Every cited CONTEXT item within `radiusKm` of (lat, lon), ordered ONLY by distance.
export function computeNearby(
  lat: number,
  lon: number,
  radiusKm: number,
  data: AppData
): NearbyItem[] {
  const hits: NearbyItem[] = [];
  for (const s of SOURCES) {
    const items = s.items(data);
    if (!items) continue;
    const src = s.source(data);
    for (const it of items) {
      if (typeof it.lat !== 'number' || typeof it.lon !== 'number') continue;
      const km = haversineKm(lat, lon, it.lat, it.lon);
      if (km > radiusKm) continue;
      hits.push({
        layer: s.layer,
        label: s.label,
        km: Math.round(km * 10) / 10,
        place: placeOf(it),
        detail: s.detail(it),
        url: s.url ? s.url(it) : null,
        source: src,
      });
    }
  }
  hits.sort((a, b) => a.km - b.km); // distance only — never by severity / evidence density
  return hits;
}

export interface FamilyCount {
  layer: string;
  label: string;
  count: number;
}

// Per-FAMILY counts of co-located cited context within a radius — deliberately NOT summed
// into one number. A single "nearby total" you could sort by is a risk score wearing a
// count's clothes ("Hormuz 6, Suez 3" reads as a ranking); keeping the families separate +
// unsorted keeps it an honest roster of cited receipts, never a leaderboard.
export function nearbyFamilyCounts(
  lat: number,
  lon: number,
  radiusKm: number,
  data: AppData
): FamilyCount[] {
  const items = computeNearby(lat, lon, radiusKm, data);
  const byLayer = new Map<string, FamilyCount>();
  for (const s of SOURCES) byLayer.set(s.layer, { layer: s.layer, label: s.label, count: 0 });
  for (const it of items) {
    const f = byLayer.get(it.layer);
    if (f) f.count += 1;
  }
  return [...byLayer.values()].filter((f) => f.count > 0);
}
