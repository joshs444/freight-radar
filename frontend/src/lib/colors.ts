// Light-theme marks: deep amber chokepoints, slate port-dust, soft slate lanes.
export const AMBER = [230, 122, 14];
export const PORT = [71, 85, 105];
export const LANE = [128, 138, 158];
export const CYAN = [13, 148, 136]; // teal accent (used sparingly)
export const QUAKE = [140, 94, 88]; // muted terracotta for USGS earthquake dots (context)
export const EVENT = [200, 120, 40]; // burnt orange for NASA EONET natural-event dots (context)
export const WAVE = [40, 110, 170]; // steel blue for Open-Meteo marine wave-height dots (context)
export const TIDE = [56, 154, 156]; // teal-cyan for NOAA CO-OPS water-level dots at US ports (context)
export const RIVER = [70, 130, 80]; // muted river-green for USGS gauge river-stage dots (context)

// GDACS official hazard-alert dots, coloured by the alert level GDACS assigns (RED/ORANGE/
// GREEN) — shown exactly as published, a cited corroborating alert, never a stated cause.
const HAZARD_BY_LEVEL: Record<string, [number, number, number]> = {
  RED: [198, 52, 52],
  ORANGE: [214, 130, 38],
  GREEN: [110, 140, 96],
};
const HAZARD_FALLBACK: [number, number, number] = [150, 120, 110];
export const hazardColor = (level: string | null | undefined): [number, number, number] =>
  HAZARD_BY_LEVEL[(level ?? '').toUpperCase()] ?? HAZARD_FALLBACK;

// Severity ramp 0 -> 100 : slate -> amber -> red, tuned to read on a light bg.
// No green (green = "all clear", wrong for an alert). Muted, not neon.
const RAMP: [number, number[]][] = [
  [0, [96, 116, 146]],
  [40, [223, 150, 52]],
  [70, [223, 110, 52]],
  [100, [214, 66, 66]],
];

// Flag disruption CATEGORIES — colour each anomaly by what it IS (not just how severe), so the map
// reads as multi-type at a glance: a strait/port collapse looks different from a congestion backlog,
// a cargo-mix change, or a fleet-size shift. `id` is the legend/filter key; each kind maps into one
// family. These doubles as the globe legend AND the sub-toggle set (LayerPanel).
export const FLAG_CATEGORIES: {
  id: string;
  label: string;
  color: [number, number, number];
  kinds: string[];
}[] = [
  {
    id: 'collapse',
    label: 'Collapse / drop',
    color: [192, 57, 43], // crimson — throughput fell hard (the alarming disruptions)
    kinds: [
      'chokepoint_transit_collapse',
      'chokepoint_persistent_collapse',
      'port_activity_drop',
      'cape_reroute',
    ],
  },
  {
    id: 'congestion',
    label: 'Congestion / surge',
    color: [217, 119, 6], // amber — backlog / buildup
    kinds: ['port_congestion_spike', 'chokepoint_transit_spike'],
  },
  {
    id: 'cargo',
    label: 'Cargo-mix shift',
    color: [37, 99, 235], // blue — a specific cargo type moved
    kinds: ['port_cargo_type_drop', 'port_cargo_type_spike'],
  },
  {
    id: 'fleet',
    label: 'Fleet-size shift',
    color: [139, 92, 176], // purple — vessel-size composition changed
    kinds: ['chokepoint_vessel_size_shift'],
  },
];
const FLAG_CAT_FALLBACK = {
  id: 'other',
  label: 'Other',
  color: [120, 120, 130] as [number, number, number],
  kinds: [] as string[],
};
const KIND_TO_CAT: Record<string, (typeof FLAG_CATEGORIES)[number]> = {};
for (const c of FLAG_CATEGORIES) for (const k of c.kinds) KIND_TO_CAT[k] = c;

/** The category a flag kind belongs to (for colour, legend, and sub-toggle filtering). */
export function flagCategory(kind: string) {
  return KIND_TO_CAT[kind] ?? FLAG_CAT_FALLBACK;
}
/** A flag's RGBA coloured by its disruption TYPE (not severity). */
export function flagTypeColor(kind: string, alpha = 255): [number, number, number, number] {
  const c = flagCategory(kind).color;
  return [c[0], c[1], c[2], alpha];
}
export const flagTypeCss = (kind: string): string => {
  const c = flagCategory(kind).color;
  return `rgb(${c[0]}, ${c[1]}, ${c[2]})`;
};

export function severityColor(
  s: number | null | undefined,
  alpha = 255
): [number, number, number, number] {
  const v = Math.max(0, Math.min(100, s ?? 0));
  let lo = RAMP[0];
  let hi = RAMP[RAMP.length - 1];
  for (let i = 0; i < RAMP.length - 1; i++) {
    if (v >= RAMP[i][0] && v <= RAMP[i + 1][0]) {
      lo = RAMP[i];
      hi = RAMP[i + 1];
      break;
    }
  }
  const t = hi[0] === lo[0] ? 0 : (v - lo[0]) / (hi[0] - lo[0]);
  const c = lo[1].map((ch, i) => Math.round(ch + (hi[1][i] - ch) * t));
  return [c[0], c[1], c[2], alpha];
}

export const severityCss = (s: number | null | undefined): string => {
  const [r, g, b] = severityColor(s);
  return `rgb(${r}, ${g}, ${b})`;
};

// GDELT world-news dots, coloured by topic so "different types of news show
// differently". Chosen to stay clear of the freight marks (amber chokepoints,
// slate ports, storm-blue) and the severity reds — these read as a distinct
// "context" family. Order = the legend order.
export const NEWS_CATEGORIES: { key: string; label: string; color: [number, number, number] }[] = [
  { key: 'economy', label: 'Economy & markets', color: [79, 70, 229] }, // indigo
  { key: 'trade', label: 'Trade & logistics', color: [13, 148, 136] }, // teal
  { key: 'energy', label: 'Energy', color: [161, 98, 7] }, // bronze
  { key: 'conflict', label: 'Conflict & security', color: [190, 24, 93] }, // magenta-rose
  { key: 'disaster', label: 'Disaster & hazard', color: [124, 58, 237] }, // violet
];
const NEWS_FALLBACK: [number, number, number] = [110, 100, 140];
const NEWS_BY_KEY: Record<string, [number, number, number]> = Object.fromEntries(
  NEWS_CATEGORIES.map((c) => [c.key, c.color])
);
export const newsCategoryColor = (key: string): [number, number, number] =>
  NEWS_BY_KEY[key] ?? NEWS_FALLBACK;
export const rgbCss = (c: [number, number, number]): string => `rgb(${c[0]}, ${c[1]}, ${c[2]})`;

// Stress-index level → color/tint, matching the backend's calm/elevated/high/severe.
export const STRESS_LEVELS = {
  calm: { color: '#3f7a5a', tint: '#eef6f1', edge: '#cfe6d9' },
  elevated: { color: '#b07b1e', tint: '#fbf4e6', edge: '#f0e2c4' },
  high: { color: '#c2611f', tint: '#fbeee2', edge: '#f1d8bf' },
  severe: { color: '#c0392b', tint: '#fbecea', edge: '#f1cdc8' },
};
export const stressLevel = (label: string | null | undefined) =>
  STRESS_LEVELS[label as keyof typeof STRESS_LEVELS] || STRESS_LEVELS.calm;
