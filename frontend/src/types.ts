// The typed contract between the Python publisher and this React reader.
//
// Each interface mirrors a sidecar JSON the backend emits (export_snapshot.py,
// detect/detectors.py, weather.py, wind.py, sidecar/ais_consumer.py, narrative/*).
// This is the single source of truth for the data layer: useData() returns AppData,
// every component reads its props out of these shapes, and useMonitorModel derives
// MonitorEntity rows from them. Optional fields are genuinely optional in the JSON
// (a sidecar may be absent, or a record may omit a key); `?` and `| null` reflect
// what the emitters actually produce.

// ---- shared primitives -----------------------------------------------------

/** A low / expected / high money band (USD). */
export interface CostBand {
  low: number;
  expected: number;
  high: number;
}

/** Vessel-type mix as fractions that sum to ~1. */
export interface CargoMix {
  container: number;
  tanker: number;
  dry_bulk: number;
  general_cargo: number;
  roro: number;
}

// ---- snapshot.json ---------------------------------------------------------

export interface SnapshotChokepoint {
  portid: string;
  name: string;
  country: string | null;
  lat: number;
  lon: number;
  industry: string;
  n_total: number;
  n_container: number;
  n_tanker: number;
  n_dry_bulk: number;
  capacity_total: number;
  avg_vessel_size_dwt: number;
  cargo_mix: CargoMix | null;
  baseline: number;
  pct_change: number;
  zscore: number;
  as_of: string;
}

export interface SnapshotPort {
  portid: string;
  name: string;
  country: string | null;
  lat: number;
  lon: number;
  as_of?: string;
  vessels: number;
  portcalls: number;
  cargo_mix: CargoMix | null;
  share_import?: number;
  share_export?: number;
}

export interface Snapshot {
  as_of: string;
  generated_at: string;
  source: string;
  chokepoints: SnapshotChokepoint[];
  ports: SnapshotPort[];
}

// ---- lanes.json ------------------------------------------------------------

export interface Lane {
  name: string;
  from: [number, number];
  to: [number, number];
  intensity: number;
}

// ---- flags.json (detect/detectors.py Flag + business enrichment) -----------

export interface ExposedLane {
  lane_id: string;
  from: string;
  to: string;
  item: string;
  value_usd: number;
  routing_confidence: string;
}

export interface CostStack {
  carrying_cost_of_delay_usd?: CostBand;
  reroute_premium_usd?: CostBand;
  total_cost_of_disruption_usd?: CostBand;
  working_capital_tied_up_usd?: CostBand;
}

export interface MethodLine {
  line: string;
  basis: string;
}

export interface BusinessImpact {
  exposed_value_usd: number;
  exposed_teu: number;
  exposed_lanes: ExposedLane[];
  lane_count: number;
  top_items: string[];
  routing_confidence: string;
  est_delay_days: CostBand;
  cost_stack: CostStack;
  method: MethodLine[];
  carrying_cost_of_delay_usd?: CostBand;
  working_capital_tied_up_usd?: CostBand;
  total_cost_of_disruption_usd?: CostBand;
  carrying_rate_assumed: number;
}

/** A live tropical cyclone matched to a flag (weather.py), attached as live_storm. */
export interface StormChip {
  name: string;
  category: string;
  basin: string;
  agency: string;
  source: string;
  km: number;
  max_wind_kmh?: number;
  url?: string;
}

/** An official GDACS/IMF event corroborating a flag, attached as official_event. */
export interface OfficialEvent {
  name: string;
  type_label: string;
  alertlevel: string;
  from: string;
  to: string;
  source: string;
}

export interface Flag {
  flag_id: string;
  kind: string;
  entity: string;
  portid: string;
  lat: number;
  lon: number;
  severity: number;
  headline: string;
  brief_md: string;
  metric: string;
  value: number;
  baseline: number;
  pct_change: number;
  zscore: number;
  as_of: string;
  source: string;
  source_url: string; // registry-resolved root URL (P0-B) — clickable, never re-hardcoded
  license: string; // registry-resolved root license (P0-B)
  method: string;
  lifecycle: string;
  chokepoints?: string[]; // structured refs (H1-B) — cape_reroute carries the Red Sea legs it diverts around
  business?: BusinessImpact | null;
  live_storm?: StormChip | null;
  official_event?: OfficialEvent | null;
}

// ---- timeseries.json -------------------------------------------------------

export interface TimeseriesSeries {
  name: string;
  metric: string;
  values: number[];
}

export interface TimeseriesChokepoint {
  portid: string;
  name: string;
  lat: number;
  lon: number;
  values: number[];
}

export interface TimeseriesFlag {
  flag_id: string;
  entity: string;
  portid: string;
  lat: number;
  lon: number;
  severity: number;
  kind: string;
  headline: string;
  as_of: string;
}

export interface Timeseries {
  dates: string[];
  max_date: string;
  chokepoints: TimeseriesChokepoint[];
  flags: TimeseriesFlag[];
  series: Record<string, TimeseriesSeries>;
}

// ---- ships.json (sidecar/ais_consumer.py) ----------------------------------

export interface Vessel {
  mmsi: string;
  lon: number;
  lat: number;
  heading: number;
  type: string;
  name: string;
}

export interface Ships {
  mode: string;
  note: string;
  source: string;
  generated_at: string;
  count: number;
  vessels: Vessel[];
}

// toggleable globe overlays (the LayerPanel + the buildLayers visibility gate).
// The LayerId union, default visibility, panel sections, and the useData fetch
// manifest are GENERATED from the Python registry (registry/layers.py -> layers.gen.ts),
// so this contract can't drift from the backend. Re-exported here so existing
// `import { LayerId } from '../types.ts'` callers keep working unchanged.
export type { LayerId, LayerVisibility } from './lib/layers.gen.ts';

// The generated CONTEXT wrappers are also USED below (the AppData payload), so bring them
// into local scope; the per-section re-export lines further down expose them to external
// `from '../types'` importers (a re-export alone is not a local binding).
import type {
  Quakes, Eonet, Marine, Tides, Streamflow, Disruptions, Gatun,
} from './types.gen.ts';

// the two ways to read the same data: explore-by-poking globe, or scan-and-sort board
export type AppView = 'globe' | 'board' | 'data' | 'ledger';

// ---- exposure.json ---------------------------------------------------------

export interface ExposureSummary {
  total_flows: number;
  total_value_usd: number;
  exposed_lanes: number;
  exposed_value_usd: number;
  carrying_cost_of_delay_usd: CostBand;
  working_capital_tied_up_usd: CostBand;
  total_cost_of_disruption_usd: CostBand;
  carrying_rate_assumed: number;
  active_disruptions_hitting_you: number;
  lanes_with_known_route: number;
  coverage_pct: number;
}

// ---- news.json -------------------------------------------------------------

export interface Article {
  title: string;
  url: string;
  source: string;
  published: string;
}

export interface NewsEntry {
  entity: string;
  items: Article[];
  relation: string;
  disclaimer: string;
  outlet_count: number;
}

export interface News {
  generated_at: string;
  search_date: string;
  items: Record<string, NewsEntry>;
}

// ---- news_geo.json (GDELT geo-tagged world-news dots — a CONTEXT layer) -----
// Distinct from news.json above: this is a standalone globe overlay, one dot per
// real geo-located article in a recent GDELT window, categorised by topic. It carries
// NO computed metric and is never a stated cause of a freight number — click a dot to
// read the cited source.

export interface NewsGeoItem {
  lat: number;
  lon: number;
  category: string; // economy | energy | trade | conflict | disaster
  category_label: string;
  place: string;
  domain: string;
  url: string;
  seen: string; // 'YYYY-MM-DD HH:MMZ'
}

export interface NewsGeo {
  generated_at: string;
  as_of: string;
  window: string; // the GDELT slice timestamp this snapshot was pulled at
  source: string;
  source_url: string;
  disclaimer: string;
  counts: Record<string, number>;
  items: NewsGeoItem[];
}

// ---- quakes.json (USGS M4+ earthquakes — a CONTEXT layer) ------------------
// One dot per observed M4.0+ event in the past 7 days, sized by magnitude. Carries no
// computed metric and is never a stated cause of a freight number — click to open the
// USGS event page. QuakeItem + Quakes are GENERATED from registry/shapes.py (types.gen.ts).
export type { QuakeItem, Quakes } from './types.gen.ts';

// ---- market.json -----------------------------------------------------------

export interface MarketIndicator {
  name: string;
  unit: string;
  value: number;
  change_pct: number;
  change_basis: string;
  as_of: string;
  source: string;
  source_url: string;
  stale: boolean;
  estimate?: boolean;
  basis?: string;
}

export interface MarketLink {
  entity: string;
  linked: string[];
  relation: string;
  disclaimer: string;
}

export interface Market {
  generated_at: string;
  indicators: Record<string, MarketIndicator>;
  items: Record<string, MarketLink>;
  disclaimer: string;
}

// ---- stress.json (narrative stress index) ----------------------------------

export interface StressContributor {
  portid: string;
  name: string;
  lat: number;
  lon: number;
  weight: number;
  stress: number;
  contribution: number;
  now: number;
  normal: number;
  pct_vs_normal: number;
}

export interface StressMover {
  portid: string;
  name: string;
  delta_stress: number;
  direction: string;
  days: number;
}

export interface Stress {
  available: boolean;
  index: number;
  label: string;
  breadth: number;
  depth: number;
  as_of: string;
  wow_delta: number;
  wow_direction: string;
  chokepoints_total: number;
  chokepoints_disrupted: number;
  disrupted_history: number[];
  history: number[];
  history_dates: string[];
  spark30: number[];
  contributors: StressContributor[];
  fastest_deteriorating?: StressMover | null;
  most_improved?: StressMover | null;
  method: string;
  source: string;
  generated_at: string;
}

// ---- brief.json ------------------------------------------------------------

export interface BriefBullet {
  kind: string;
  text: string;
  cites: string[];
  note?: string;
  portid?: string;
}

export interface Brief {
  generated_at: string;
  as_of: string;
  headline: string;
  stress_index: number;
  stress_label: string;
  active_count: number;
  new_this_week: number;
  bullets: BriefBullet[];
  source: string;
}

// ---- events.json -----------------------------------------------------------

export interface LedgerEvent {
  seq: number;
  at: string;
  type: string;
  flag_id: string;
  entity: string;
  kind: string;
  severity: number;
  pct_change: number;
  portid: string;
}

export interface Events {
  generated_at: string;
  as_of: string;
  baseline_run: boolean;
  event_count: number;
  new_this_run: number;
  events: LedgerEvent[];
}

// ---- world.json ------------------------------------------------------------

export interface WorldMetric {
  key: string;
  label: string;
  sublabel: string;
  unit: string;
  value: number;
  vs7_pct: number;
  trend: string;
  spark: number[];
  as_of: string;
}

export interface World {
  available: boolean;
  as_of: string;
  ports_as_of: string;
  chokepoints: number;
  ports_active: number;
  metrics: WorldMetric[];
  transit_mix: { container: number; tanker: number; dry_bulk: number };
  source: string;
  generated_at: string;
}

// ---- disruptions.json ------------------------------------------------------
// DisruptionEvent + Disruptions are GENERATED from registry/shapes.py (types.gen.ts).
export type { DisruptionEvent, Disruptions } from './types.gen.ts';

// ---- gatun.json (Panama Canal lake-level leading indicator) ----------------
// GatunProjection + Gatun are GENERATED from registry/shapes.py (types.gen.ts).
export type { GatunProjection, Gatun } from './types.gen.ts';

// ---- weather.json (live storm layer) ---------------------------------------

export interface Storm {
  id: string;
  name: string;
  category: string;
  basin: string;
  lat: number;
  lon: number;
  source: string;
  agency: string;
  max_wind_kmh: number;
  advisory: string;
  cone_url: string;
  url: string;
}

export interface Weather {
  generated_at: string;
  as_of: string;
  source: string;
  match_radius_km: number;
  storms: Storm[];
  counts: { active_storms: number; nhc: number; gdacs: number; flags_matched: number };
}

// ---- wind.json (NOAA GFS ambient wind layer) -------------------------------

export interface WindFrame {
  fhour: number;
  valid: string;
  image: string;
}
export interface Wind {
  generated_at: string;
  as_of: string;
  source: string;
  cycle: string;
  image: string;
  frames?: WindFrame[];
  width: number;
  height: number;
  imageUnscale: [number, number];
  bounds: [number, number, number, number];
}

// ---- history.json (the 2019→now "play through history" view) ---------------

export interface HistoryEvent {
  id: string;
  title: string;
  date: string;
  from?: string;
  to?: string;
  blurb: string;
  source: string;
  url: string;
}

export interface HistoryChokepoint {
  portid: string;
  name: string;
  lat: number;
  lon: number;
  normal: number;
  values: number[];
}

export interface History {
  generated_at: string;
  resolution: string;
  range: { start: string; end: string };
  dates: string[];
  stress: number[];
  chokepoints: HistoryChokepoint[];
  events: HistoryEvent[];
  method: string;
  source: string;
}

// ---- eonet / marine / tides / streamflow (CONTEXT dot layers) --------------
// All four (wrapper + item) are GENERATED from registry/shapes.py (types.gen.ts) — the same
// shape registry the data contracts derive from. Re-exported so `from '../types'` keeps working.
export type { EonetItem, Eonet } from './types.gen.ts';
export type { MarineItem, Marine } from './types.gen.ts';
export type { TideItem, Tides } from './types.gen.ts';
export type { StreamflowItem, Streamflow } from './types.gen.ts';

// ---- the full payload useData() resolves -----------------------------------

export interface AppData {
  snapshot: Snapshot;
  lanes: Lane[];
  flags: Flag[];
  timeseries: Timeseries | null;
  ships: Ships | null;
  exposure: ExposureSummary | null;
  news: News | null;
  newsGeo: NewsGeo | null;
  quakes: Quakes | null;
  eonet: Eonet | null;
  marine: Marine | null;
  tides: Tides | null;
  streamflow: Streamflow | null;
  market: Market | null;
  stress: Stress | null;
  brief: Brief | null;
  events: Events | null;
  world: World | null;
  disruptions: Disruptions | null;
  gatun: Gatun | null;
  weather: Weather | null;
  wind: Wind | null;
  signals: SignalsFdr | null;
}

// ---- cross-domain measured signals (signals_fdr.json) ----------------------
// The non-maritime measured anomalies — freight-mode rates (truckload/rail/air),
// inventories-to-sales, commodities, metals, macro, labor. National + monthly (no geo),
// so they surface as a feed panel, not globe markers. A z-score WE compute, FDR-gated.
/** One computed-anomaly point on a signal's 36-month z-track (the raw index stays cited; the z is ours). */
export interface SignalZPoint {
  date: string;
  z: number;
}
export interface SignalItem {
  family: string;
  id: string;
  name: string;
  unit: string;
  as_of: string;
  value: number;
  our_zscore: number;
  fdr_significant: boolean;
  // provenance carried through signal_pool.py (P0-A) — the full raw→computed→published→cited chain.
  source: string; // RAW cited index, e.g. "FRED — BLS Producer Price Index"
  source_url: string; // canonical home of the cited series
  method: string; // the z-score WE compute over the cited series (never the source's own claim)
  z_series: SignalZPoint[]; // 36-pt computed anomaly track (the sparkline)
  fenced: string; // 'national' — no lat/lon, never place-attributable (P2-A's fence reads this)
}
export interface SignalsFdr {
  method?: string;
  disclaimer?: string;
  q?: number;
  families?: string[];
  counts?: { tested?: number; significant?: number; expected_false?: number };
  items: SignalItem[];
}

// ---- derived UI shapes -----------------------------------------------------

/** One row in the Monitor feed / one marker on the globe: a chokepoint, a flagged
 *  port, or a top port, normalised by useMonitorModel into a single shape. */
export interface MonitorEntity {
  id: string;
  name: string;
  type: 'chokepoint' | 'port';
  lat: number;
  lon: number;
  metric: number | null;
  flag: Flag | null;
  severity?: number | null;
  critical: boolean;
  weight?: number;
  cargo_mix?: CargoMix | null;
  avg_vessel_size_dwt?: number;
  capacity_total?: number;
  n_total?: number;
  baseline?: number;
  vessels?: number;
  share_import?: number;
  share_export?: number;
  country?: string | null;
  as_of?: string; // the snapshot data date — feeds the unflagged port/chokepoint trace (P1-B)
  relevance?: number; // importance × magnitude × corroboration; see lib/relevance.ts
}

/** The globe only needs a subset of each marker's fields. Both the live shapes
 *  (SnapshotChokepoint, Flag) and the scrub-replay shapes (a reduced chokepoint and
 *  TimeseriesFlag) satisfy these, so the globe renders either without a cast. */
export interface GlobeChokepoint {
  portid: string;
  name: string;
  lat: number;
  lon: number;
  n_total: number;
  pct_change: number | null;
}
export interface GlobeFlag {
  flag_id: string;
  entity: string;
  portid: string;
  lat: number;
  lon: number;
  severity: number;
  kind: string;
  headline: string;
  pct_change?: number;
  relevance?: number; // drives marker size: the needle reads bigger than the blips
}
export type GlobeSnapshot = Omit<Snapshot, 'chokepoints'> & { chokepoints: GlobeChokepoint[] };

/** The scrub-aware view of the globe (snapshot + which flags have fired). */
export interface GlobeView {
  snapshot: GlobeSnapshot | null;
  flags: GlobeFlag[];
}

/** The imperative handle the Globe exposes to the App for flying to an entity. */
export interface MapApi {
  flyTo: (lon: number, lat: number) => void;
}
