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
  method: string;
  lifecycle: string;
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
// USGS event page.

export interface QuakeItem {
  id: string;
  mag: number;
  place: string;
  lat: number;
  lon: number;
  depth_km: number | null;
  time: string;
  tsunami: boolean;
  url: string;
}

export interface Quakes {
  generated_at: string;
  as_of: string;
  source: string;
  source_url: string;
  disclaimer: string;
  min_mag: number;
  counts: { total: number; m5plus: number };
  items: QuakeItem[];
}

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

export interface DisruptionEvent {
  eventid: number;
  type: string;
  type_label: string;
  name: string;
  alertlevel: string;
  country: string;
  from: string;
  to: string;
  lat: number;
  lon: number;
  severity: string;
  affected_ports: { portid: string; name: string }[];
  n_affected_ports: number;
  near_chokepoints: { portid: string; name: string; km: number }[];
  affected_population: string;
}

export interface Disruptions {
  generated_at: string;
  as_of: string;
  window_days: number;
  source: string;
  source_url: string;
  events: DisruptionEvent[];
  counts: { events: number; red: number; flags_corroborated: number };
}

// ---- gatun.json (Panama Canal lake-level leading indicator) ----------------

export interface GatunProjection {
  date: string;
  level_ft: number;
  surcharge_pct: number;
  neopanamax_draft_ft: number;
  panamax_draft_ft: number;
}

export interface Gatun {
  available: boolean;
  portid: string;
  name: string;
  as_of: string;
  current_level_ft: number;
  pctile_alltime: number;
  change_30d_ft: number;
  change_365d_ft: number;
  level_spark: number[];
  normal_max_draft_ft: number;
  min_projected_neopanamax_draft_ft: number;
  draft_restricted: boolean;
  surcharge_pct_now: number;
  projection: GatunProjection[];
  source: string;
  source_url: string;
  disclaimer: string;
  lat: number;
  lon: number;
  generated_at: string;
}

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

// ---- eonet.json (NASA EONET natural events — a CONTEXT globe layer) ---------
export interface EonetItem {
  id: string;
  title: string;
  category: string;
  lat: number;
  lon: number;
  date: string;
  url: string;
}
export interface Eonet {
  generated_at: string;
  as_of: string;
  source: string;
  source_url: string;
  disclaimer: string;
  counts: { events: number; by_category: Record<string, number> };
  items: EonetItem[];
}

// ---- marine.json (Open-Meteo wave height at chokepoints — a CONTEXT globe layer) ----
export interface MarineItem {
  name: string;
  lat: number;
  lon: number;
  wave_height_m: number;
  wave_period_s: number | null;
  observed_at: string;
}
export interface Marine {
  generated_at: string;
  as_of: string;
  source: string;
  source_url: string;
  disclaimer: string;
  counts: { chokepoints: number };
  items: MarineItem[];
}

export interface TideItem {
  port: string;
  station: string;
  lat: number;
  lon: number;
  water_level_ft: number;
  observed_at: string;
  url: string;
}
export interface Tides {
  generated_at: string;
  as_of: string;
  source: string;
  source_url: string;
  disclaimer: string;
  counts: { ports: number };
  items: TideItem[];
}

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
  market: Market | null;
  stress: Stress | null;
  brief: Brief | null;
  events: Events | null;
  world: World | null;
  disruptions: Disruptions | null;
  gatun: Gatun | null;
  weather: Weather | null;
  wind: Wind | null;
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
