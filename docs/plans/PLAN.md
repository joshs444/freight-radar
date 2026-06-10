# Freight Radar — Build Plan

A striking, living **dark-globe map of ocean freight** where the 28 IMF-tracked maritime
chokepoints + top ports glow by real daily activity, and a **durable Temporal agent
auto-flags disruptions** (chokepoint transit collapse, port congestion spike, Cape-of-Good-Hope
rerouting) into a severity-ranked "current issues" rail — each flag click-expanding into a
plain-English "what's happening + why" brief.

**Working name:** Freight Radar (alt: "Chokepoint"). A flagship build in a real
ocean-freight domain; extends the existing durable-Temporal work.

---

## The one decisive architectural seam
The app reads **ONLY from local DuckDB tables**, never from any upstream directly.
- **Tier 1 — RELIABLE BACKBONE (load-bearing):** IMF PortWatch (free, no key, verified live).
  *All flags + severity are computed off this tier.*
- **Tier 2 — LIVE GARNISH (optional, non-load-bearing):** aisstream.io WebSocket for moving-ship
  dots/trails in hotspot bboxes. Write-only to a TTL table the flag engine never reads;
  degrades to an "AIS offline" badge. (Had a Mar-2026 outage — never load-bearing.)
- **Tier 3 — OPTIONAL HISTORICAL:** NOAA Marine Cadastre AIS GeoParquet (DuckDB httpfs) for
  pretty US-EEZ historical trails.

**Honesty rule (in the UI, not just the README):** PortWatch is **daily-granularity, refreshed
weekly** (Tuesdays ~9am ET). The value is the auto-flagging + attribution, NOT refresh speed.
Every tile shows its source + "data as of `<max date>`". Never say "live" for the backbone.

---

## Verified data sources (checked live during design)
Host factory: `https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services`
*(NOTE: an old org id `weJ1QsnbMRgolu6q` 400s — use the one above.)*

| Service | Use | Notes |
|---|---|---|
| `Daily_Chokepoints_Data/FeatureServer/0/query` | chokepoint time series | fields: `date`(ISO **string** 'YYYY-MM-DD'), `portid`('chokepoint1'..'28'), `n_container/_dry_bulk/_general_cargo/_roro/_tanker/_cargo/_total`, `capacity_*`. **No geometry.** |
| `Daily_Ports_Data/FeatureServer/0/query` | port time series | `portid`, `portcalls*`, `import*`, `export*`. **No geometry, no capacity.** |
| `PortWatch_chokepoints_database/FeatureServer/0/query` | **28 chokepoints** w/ geom | `portid,fullname,country,lat,lon,LOCODE,industry_top1..3` |
| `PortWatch_ports_database/FeatureServer/0/query` | **~2065 ports** w/ geom | same shape |
| `portwatch_disruptions_database` | curated disruption events | use to corroborate LLM attribution |

Query patterns: `?where=1=1&outFields=*&f=json` · latest-N: `orderByFields=date DESC&resultRecordCount=30` ·
date window: `where=date>=DATE '2026-05-01'` · pagination: `&resultOffset=1000&resultRecordCount=1000` loop until `exceededTransferLimit=false` (1000-cap).
**Daily layers have NO lat/lon — join to the `*_database` reference layers on `portid` (assert >95% coverage).**

aisstream (garnish): `wss://stream.aisstream.io/v0/stream` — send subscribe JSON `<3s` of connect:
`{"APIKey":"<key>","BoundingBoxes":[[[swLat,swLon],[neLat,neLon]]],"FilterMessageTypes":["PositionReport","ShipStaticData"]}`.

NOAA (optional): `read_parquet('https://ocmgeodatastor1.blob.core.windows.net/marinecadastre/...')` via DuckDB httpfs.

---

## Stack
- **Data/ingest:** Python 3.11+, `httpx` (async), verified query strings + `resultOffset` pagination
- **Storage/detection substrate:** **DuckDB** (single file; window functions for rolling baselines; `httpfs` for NOAA)
- **Detection brain:** numpy/pandas (rolling z-score + CUSUM), `statsmodels` STL(period=7, robust=True), `ruptures` PELT(rbf) change-point gate — config-driven via one YAML
- **Orchestration:** **Temporal** (`temporalio`) — one durable `FreightRadarWorkflow` on a Schedule, 5 activities, RetryPolicy + signals/queries; `temporal server start-dev --db-filename` so schedules survive restart. *Extends Josh's durable-agent repo.*
- **LLM attribution:** thin gateway, fires ONLY on new/escalating flags; **numbers always computed in Python** and string-substituted (LLM never invents numbers); template-first + optional local Ollama polish (zero cost)
- **Backend API:** FastAPI read-only (`/api/snapshot`, `/api/flags`, `/api/ships`, `/api/health`; ETag)
- **Frontend:** React + Vite + `react-map-gl/maplibre`; **MapLibre GL JS v5 native globe** (`setProjection({type:'globe'})`) + atmosphere; **deck.gl v9+** via `MapboxOverlay(interleaved:true)` — **reject `_GlobeView`**. Layers: ScatterplotLayer (glow), ArcLayer (lanes), IconLayer (pulsing flags), TripsLayer (live trails). Basemap: self-hosted Protomaps `.pmtiles` dark (no Mapbox token)
- **Deploy:** docker-compose locally; frontend free-static (Vercel/CF/GH Pages) degrading to last-good snapshot; always-on worker on Josh's existing EC2

---

## Waves (reliable-first, flaky-last)

### Wave 0 — Verified data plumbing (the seam) · ~1–2 days
Stand up the only thing the app reads: DuckDB tables fed by the verified PortWatch backbone.
- `ingest/portwatch.py` (httpx + verified queries + pagination); `ingest/dims.py` (load 28 chokepoints + ~2065 ports w/ geom, reproject)
- `storage/schema.sql`: `dim_chokepoint`, `dim_port`, `fct_chokepoint_daily(PK portid,date)`, `fct_port_daily(PK portid,date)`, `meta_ingest_runs`, `meta_source_status`
- Backfill 120–180d, then incremental (trailing 3d re-pull)
- `tests/test_portwatch_contract.py` — LIVE receipt: rows returned, date is ISO string, >95% portid→geometry join
- **DoD:** backfill produces a DuckDB where `max(date)` is recent, join resolves >95%, contract test passes.

### Wave 1 — STRIKING glowing globe from one snapshot (the whoa frame) · ~3–4 days
The GIF-able money shot, from a single static snapshot. Zero Temporal/streaming/runtime-backend.
- One-shot exporter → `data/snapshot.json` (ports + 28 chokepoints w/ activity) + hardcoded `lanes.json`
- React+Vite; MapLibre v5 globe + atmosphere; Protomaps dark basemap; deck.gl `MapboxOverlay(interleaved)`
- Layers: ScatterplotLayer glow (radius ~ √vessel_count, additive halo) + ArcLayer lanes + IconLayer pulsing flags
- Severity-ranked "Current Issues" rail + click-popover brief; every tile shows source + "as of `<date>`"
- Static deploy (proves free/static path)
- **DoD:** a deployed static URL renders a dark 3D earth with atmosphere, chokepoints/ports glowing by real activity, lane arcs correct, a few canned flags clickable.

### Wave 2 — Detection brain: real flags + briefs over history · ~3–4 days
Make every flag a genuine detected anomaly with computed numbers.
- STL(7, robust) residual → rolling z (window=28; |z|≥3 collapse / ≥3.5 spike) over 28 chokepoints + top ports
- Flag classes: `chokepoint_transit_collapse`, `port_congestion_spike`; explicit visible **severity 0–100** = magnitude × persistence × economic-weight
- `fct_flags` populated (zscore, baseline, pct_change, headline, brief_md, lifecycle); template-first briefs (numbers in Python)
- `config/detection.yaml`; `tests/test_detectors.py` (fires on real Suez collapse; does NOT fire on weekend seasonality)
- **DoD:** exporter emits `flags.json` from real history; map shows genuine anomalies ranked by visible severity, each brief contains the real numbers.

### Wave 3 — Durable Temporal loop (the durable core) · ~3–4 days
Wrap fetch→detect→attribute→publish in a durable Temporal workflow on a Schedule — visibly always-on, crash-durable.
- `FreightRadarWorkflow` (5 activities: fetch → compute+detect → llm_attribute → assemble → publish); RetryPolicy; continue-as-new
- Idempotent `ensure_schedule()`; **flag dedup ledger** `flag_id=sha1(kind|entity|iso_week)` (attribute only `attributed_at IS NULL`)
- Atomic snapshot publish + version bump; FastAPI read-only surface; docker-compose (temporal `--db-filename` on a volume, worker, schedule-init, api)
- `tests/test_dedup_free_rerun.py`: a second identical run makes ZERO LLM calls
- **DoD:** `docker-compose up` brings the loop online; Schedule publishes fresh snapshots the map picks up; kill-worker-mid-run → restart → schedule resumes (the receipt demo).

### Wave 4 — Time-scrubber replay (the GIF-able collapse) · ~2 days
- Workflow also writes `timeseries/<date>.json`; `TimeScrubber.tsx` swaps the daily snapshot driving deck.gl; play/pause; attract-mode auto-plays the most dramatic recent window
- **DoD:** scrubbing visibly replays a real chokepoint collapse (glow dimming + a red flag firing on its actual detected date).

### Wave 5 — Detection depth + Cape-reroute + lifecycle hardening · ~3–4 days
- Add CUSUM + ruptures PELT gate (z OR CUSUM trips AND a PELT breakpoint within 7d)
- **Cape-reroute divergence detector** (Red Sea chokepoints DOWN while Cape bypass UP in a 14d window) — the signature story
- Full lifecycle (new/ongoing/escalated/resolved w/ hysteresis); trailing-14d re-pull (PortWatch values are revisable); holiday calendar (Lunar New Year/Christmas) so benign demand dips aren't called crises
- LLM gated to new/escalating; require ≥1 cited dated source; prefer the curated `disruptions_database` event
- **DoD:** Cape-reroute flag fires on the real Red Sea↔Cape signal; rail is stable (no flicker); revisions absorbed; holidays don't false-positive.

### Wave 6 — Live-AIS garnish (optional, non-load-bearing) + historical trails · ~2–3 days
- `sidecar/ais_consumer.py` (SEPARATE asyncio process, NOT a Temporal activity) holds the WebSocket; writes `ships.json`; flips `ais_status`; docker-compose under `profile: garnish`
- deck.gl TripsLayer fed from `ships.json` (rAF currentTime, capped trail, prune stale); empty-safe
- Optional NOAA historical trails precomputed via DuckDB httpfs
- **DoD:** when healthy, ship dots/trails animate in 2–3 hotspots with a "best-effort" badge; killing the socket leaves the map + every number unaffected.

### Wave 7 — Polish + public framing · ~2–3 days
- Bloom/glow, fly-to on flag click, auto-rotating attract globe, per-chokepoint severity sparkline
- UI truthfulness: source + "as of `<date>`" everywhere; backbone labeled "daily-granularity, refreshed weekly by IMF"; AIS labeled best-effort
- README leads with the auto-flag GIF + a "How it stays honest" section; deploy story documented
- **DoD:** polished deployed demo, honest framing throughout, README hero GIF — ready for a first-time visitor.

---

## Demo milestones (earliest striking first)
1. **W1** — dark globe, real chokepoints/ports glowing, clickable flags. *(the whoa frame)*
2. **W2** — flags are REAL ("Suez transit fell 41% vs 28-day norm — 17 vs ~29/day"), with source + as-of.
3. **W3** — durable Temporal agent visibly always-on; kill+restart → resumes. *(the durability receipt)*
4. **W4** — scrub the timeline, replay a real chokepoint collapse. *(the narrative GIF)*
5. **W5** — the Cape-of-Good-Hope reroute story fires, cited.
6. **W6** — optional live ship dots; killing the socket changes nothing.
7. **W7** — polished hero, README GIF, "How it stays honest."

## Top risks (baked into the waves)
- Right org id is `weJ1QsnbMYJlCHdG` (the other 400s).
- `date` is an **ISO string**, not epoch-ms — don't corrupt it.
- Daily layers carry **no geometry** — the `portid` join is mandatory.
- **"Live" is a trap** — PortWatch refreshes weekly; show the data's own max(date).
- Values are **revisable estimates** — trailing-14d re-pull each run.
- Weekly seasonality + holidays → use STL(period=7) + a holiday calendar or the rail floods with false positives.
- aisstream is flaky → garnish only, late, degrades to nothing.
- Don't use deck.gl `_GlobeView` (experimental) — MapLibre globe + interleaved overlay instead.
