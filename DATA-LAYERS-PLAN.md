# Freight Radar — Data Layers Expansion Plan

## Framing

Freight Radar already proves the hard part: a durable Temporal loop ingests free IMF PortWatch ocean-freight data into DuckDB, detectors (STL + z-score + PELT + persistent-level-shift) auto-flag chokepoint/port disruptions, and a fan of **static sidecar JSON files** in `frontend/public/data/` (`snapshot.json`, `flags.json`, `timeseries.json`, `exposure.json`, `news.json`, `ships.json`) gets loaded **optionally** by the React feed (`.catch(()=>null)`, so a missing layer just hides). The existing `BUSINESS-PLAN.md` covers the first-party $-exposure layer (flags → user trade dataset → dollar exposure); this plan does **not** touch or duplicate that — it composes around it.

This plan adds **four new signal layers** that answer "what else is true around this flag, from free sources, honestly":

1. **Market impact** — oil / freight / bunker / FX context tied to each chokepoint flag.
2. **Weather / storms** — active tropical cyclones whose cone/track overlaps a flagged port or chokepoint.
3. **AIS-computed congestion** — real median dwell / anchorage-wait / Cape-rounding from vessel positions (replaces the "inferred from port calls, not direct dwell" caveat).
4. **Internal signals** — tonnage/vessel-mix from capacity fields + IMF-curated disruption-event corroboration + modeled spillover dependents, all from data already on the configured ArcGIS host.

**The order is value-per-effort, and the first wave is a refactor, not a feature.** A code review of the seam found the existing optional enrichers (`export_timeseries`, `enrich_news`, `ais_consumer`) are **orphaned** — they have only `__main__`/test callers and are never run by `publish_static` (publish.py) or the Temporal workflow. So `timeseries.json` / `news.json` / `ships.json` on disk were produced by hand and go **stale on every scheduled tick**. Adding four more layers to that pattern multiplies the spaghetti. Wave 0 fixes the wiring once so every layer after it is a one-line registration.

**Non-negotiables carried into every wave:** zero/low marginal cost (free, ideally keyless — and the plan states explicitly where a source needs a key or is licence-encumbered); honesty (numbers computed from source, estimates labelled, sources cited + dated, correlation-not-causation for market/weather); extend-don't-rewrite the existing contracts.

---

## Unified signal-layer architecture

All four layers ride one generic enricher + sidecar pattern so the codebase stays flat as it grows from 6 sidecars to 10.

### The generic enricher

Every existing enricher already shares a de-facto interface — `enrich_*_from_files(flags_path, out_dir, ...) -> dict`: take the publish dir (+ `flags.json` and/or the DuckDB path), compute deterministically from source, write **exactly one** sidecar JSON, return a receipt dict. We make that explicit:

```python
# backend/freight_radar/enrich.py  (NEW, ~50 lines)
@dataclass
class EnrichCtx:
    db_path: Path
    out_dir: Path
    flags_path: Path        # data/flags.json
    as_of: str              # snapshot as_of date
    today: str

# An enricher is: (ctx: EnrichCtx) -> receipt dict
#   receipt = {"name", "sidecar", "items"|"rows", "kb", "error": str|None}

ENRICHERS: list[tuple[str, Callable[[EnrichCtx], dict], bool]] = [
    # (name,            run,                         depends_on_flags)
    ("exposure",  exposure.run,   True),   # existing, BUSINESS-PLAN.md — unchanged
    ("news",      news.run,       True),   # existing, un-orphaned by Wave 0
    ("timeseries", timeseries.run, False), # existing, un-orphaned by Wave 0
    ("market",    market.run,     True),   # Wave 1
    ("internal",  internal.run,   True),   # Wave 2 (tonnage/mix + IMF disruptions + spillovers)
    ("weather",   weather.run,    True),   # Wave 3
    ("dwell",     dwell.run,      False),  # Wave 4 (entity/portid-keyed)
]

def run_enrichers(ctx: EnrichCtx) -> dict:
    receipts = {}
    for name, run, _ in ENRICHERS:
        try:
            receipts[name] = run(ctx)            # writes one sidecar
        except Exception as e:                   # server-side .catch(()=>null)
            receipts[name] = {"name": name, "error": repr(e)}
            log.warning("enricher %s failed: %r", name, e)
    return receipts                              # one bad layer NEVER aborts publish
```

**Per-layer failure is swallowed** — the server-side mirror of the frontend's `.catch(()=>null)`. A 429 from a price API or a down RSS feed writes a `stale`/empty sidecar and the manifest still stamps.

### How each flows into the three integration points

**1. `publish_static` (the free static / GitHub-Pages path).** `publish.py:publish_static` becomes:
```
run_detection  ->  run_enrichers(ctx)  ->  export(write_flags=False)  ->  write_manifest
```
(today it hard-calls only `exposure.enrich_from_files` inline — that single line is replaced by the registry).

**2. The Temporal loop (always-on docker path).** One new activity calls the **same** `run_enrichers`:
```python
@activity.defn
async def enrich_sidecars() -> dict:        # added to ALL_ACTIVITIES, registered in worker.py
    return run_enrichers(build_ctx())
```
Inserted in `workflow.py:run` as `step("enrich", activities.enrich_sidecars, timeout_s=300)` **between `assemble` and `publish`** (it needs `flags.json` to exist; it must finish before the manifest stamps freshness). The existing 3-attempt `RetryPolicy` applies; the activity swallows per-enricher errors internally so a slow fetch never fails the durable run. **Static and live now call one code path and cannot diverge.**

**3. The React feed (`frontend/src/lib/useData.js`).** Each new layer adds exactly one line to the OPTIONAL block (never CORE — a CORE miss blanks the whole app):
```js
getJson('data/market.json').catch(() => null),
```
and the key is threaded into `setState` and down through `App.jsx` → `DataFeed.jsx` props exactly like `news`.

### The three sidecar shapes (every layer picks one)

| Shape | Key | Existing example | Consumed in feed as |
|---|---|---|---|
| **Per-flag** | `flag.flag_id` | `news.json`, `exposure.json` | `news?.[e.flag.flag_id]`, `<X b={e.flag.business}>` |
| **Per-entity** | `portid` (`port…`/`chokepoint…`) | `timeseries.json` | `series?.[e.id]` |
| **Standalone-globe** | none | `ships.json` | `<Globe ships=… />` + legend badge |

Per-flag layers key by `flag_id` (changes weekly via the ISO-week dedup ledger). Per-entity layers key by stable `portid`. Keying wrong silently fails to render — it's the #1 wiring trap. Layer assignment: **market = per-flag**, **internal = per-flag** (disruption corroboration) + per-entity (tonnage/mix on the sparkline), **weather = per-flag**, **dwell = per-entity (portid)** + a globe overlay.

### Manifest extension (extend, don't rewrite)

`write_manifest` gains a `layers` block so `/api/health` and the UI can honestly report freshness per layer:
```json
"layers": { "market": {"present": true, "as_of": "...", "kb": 4}, "weather": {...}, "dwell": {...}, "internal": {...} }
```

---

## Wave 0 — Un-orphan the enrichers, build the registry (REFACTOR; unblocks all four)

**Goal.** Make the static path and the Temporal loop call one ordered enricher registry, so the existing orphaned sidecars (`timeseries`/`news`/`ships`) refresh on every tick and the four new layers are one-line registrations forever after.

**Deliverables.**
- `backend/freight_radar/enrich.py` — `EnrichCtx`, `ENRICHERS` registry, `run_enrichers(ctx)` (per-enricher try/except).
- Adapt the **existing** enrichers to the `run(ctx)` signature (thin wrappers around their current `*_from_files`; keep each `__main__` for standalone debugging — no rewrite).
- `publish.py:publish_static` rewritten to `run_detection -> run_enrichers(ctx) -> export -> write_manifest`.
- `temporal/activities.py`: new `enrich_sidecars` activity; appended to `ALL_ACTIVITIES`.
- `temporal/workflow.py`: `step("enrich", activities.enrich_sidecars)` inserted between `assemble` and `publish`.
- `ships.json` demo regen folded in: an orchestrator step runs `python -m freight_radar.sidecar.ais_consumer --demo` (the consumer stays a **non-Temporal** asyncio process by its own docstring; only its committed demo output joins the static build).
- `write_manifest` gains the `layers` block.
- Test (mirror `test_temporal_workflow.py`): `run_enrichers` writes every expected sidecar; **a forced single-enricher failure still produces `manifest.json` and all other sidecars** (degradation contract).
- Regenerate + **commit** `public/data/*.json` (prod is static Pages over committed JSON — "wired but not committed" = live site still stale).

**Definition of Done / receipt.**
- `grep -n "run_enrichers" publish.py activities.py` shows both drivers call the same function.
- One Temporal tick (or `python -m freight_radar.publish`) regenerates `news.json` + `timeseries.json` with a `generated_at` newer than `flags.json`'s previous value — **proving the staleness bug is fixed** (today their timestamps drift behind every tick).
- The degradation test passes: inject `raise` into one enricher, assert `manifest.json` still stamps `version: prev+1`.
- `git diff --stat public/data/` shows the regenerated sidecars committed and `deploy.yml` ships them.

---

## Wave 1 — Market impact (free, keyless-leaning, immediate) → `market.json`

**Goal.** Tie each active chokepoint flag to the prices it *plausibly touches* (crude, natgas/LNG proxy, bunker, FX, and a manually-curated container-freight figure), as dated **context** — never causation.

**Deliverables.**
- `backend/freight_radar/business/market.py` — modeled 1:1 on `news.py`: deterministic `httpx` fetch (codebase's existing client/UA), code owns every number + citation, fixed disclaimer, honest empty state, `run(ctx)`.
- **Tiered source strategy** (any single source failing degrades to `stale`):
  - **PRIMARY / licence-clean** = **FRED** `fredgraph.csv?id={DCOILBRENTEU|DCOILWTICO|DHHNGSP|DEXUSEU|DEXCHUS}` — public-domain (no redistribution restriction). *Needs a browser User-Agent (403'd a bot UA in research); 1–2 business-day lag → it's the durable/archival source.*
  - **FRESH cross-check** = **Stooq** `q/l/?s={cb.f|cl.f|ng.f|eurusd}&f=sd2t2ohlcv&h&e=csv` (verified live, keyless: WTI 96.29, natgas 3.239, EUR/USD 1.15997) and/or **Yahoo v8** `chart/{BZ=F|CL=F|NG=F|EURUSD=X|CNY=X}` (keyless, project-confirmed Brent $98).
  - `stale:true` when `as_of` is older than N days; `source`+`source_url`+`as_of` stored **per value**.
- `config/market_links.yaml` — chokepoint→instrument map (NOT hardcoded in logic): `Hormuz:[brent,natgas]`; `Suez/RedSea/BabElMandeb:[container_fbx,bunker_vlsfo,brent]`; `Panama:[wti,container_fbx]`; `Bosphorus/Kerch:[brent]`; `Malacca:[brent,container_fbx]`; others `→ []` (honest empty).
- `config/market_manual.yaml` — human-entered weekly container/BDI values (`fbx`/`wci` stamped `manual:true` + attribution). **FBX/WCI/SCFI/BDI are NOT keyless free JSON** (SCFI login-walled, BDI Baltic-Exchange-licensed, FBX/WCI attribution-gated HTML) — never scraped.
- **Bunker is modeled, not quoted:** `bunker_vlsfo = f(Brent)`, `estimate:true`, `basis:"modeled_from_brent"`, ref Ship & Bunker (which 403s bots, no public API).
- Frontend: `<MarketBlock b={e.flag.market}>` beside `<BusinessImpact>` in `DataFeed.jsx`; `getJson('data/market.json').catch(()=>null)` in `useData.js`.
- Test (mirror `test_news.py`): every indicator has `source`+`source_url`+`as_of`; every `estimate` carries `estimate:true`+`basis`; every per-flag block carries the disclaimer; a stale series flags `stale:true`; no value without provenance.

**Definition of Done / receipt.**
- `market.json` exists with `indicators.brent.value` populated from a live FRED/Stooq/Yahoo pull and a real `as_of` date, plus a Hormuz-flag block listing `linked:[brent,natgas]` with `relation:"exposure_context"` and the disclaimer.
- The honesty test passes; bunker shows `estimate:true`; `container_fbx` (if present) shows `manual:true` + attribution.
- A deliberately-broken source (point FRED at a 404) writes `stale:true` and the layer still renders — proving graceful degradation.

---

## Wave 2 — Internal signals: tonnage/mix + IMF disruption corroboration + spillovers (free, KEYLESS, data already in hand)

**Goal.** Two high-signal additions from the **same ArcGIS host already configured** (`services9.arcgis.com/weJ1QsnbMYJlCHdG`), needing zero new external dependencies — placed early because it's keyless, on-host, and the highest signal-per-effort after the refactor.

**2a — Tonnage / vessel-mix signal (detector + sidecar only; columns already in DuckDB).**
Research **disproved the task premise**: chokepoint `capacity` is **not** a throughput ceiling — it's the IMF's estimated daily cargo **tonnage that transited** (a flow), receipt: Hormuz `capacity` swung 349 → 154,946 in one week, all-time min 0. So `n_total/capacity = 1/avg-vessel-size`, **not** utilization — building a "utilization %" would be fabricated. Instead:
- Run the **existing** STL+z / persistent-level-shift detectors a **second time** on the `capacity_total` (tonnage) series per chokepoint (columns already in `fct_chokepoint_daily` — no new ingest).
- Emit per-flag `count_flagged` + `tonnage_flagged` + `signal_agreement ∈ {agree, count_only, tonnage_only, none}`. **Agreement = high-confidence real collapse** (Hormuz fires both today); **divergence = a mix-shift story, label it, don't alarm.**
- Per-entity diagnostic `avg_vessel_size_tons = capacity_total / NULLIF(n_total,0)` on the sparkline — labelled "avg cargo size of transiting vessels," never "utilization." Guard `NULLIF` on zero-traffic days.
- Optional per-cargo precision for tanker-heavy chokepoints: detector on `capacity_tanker/n_tanker` → "tanker tonnage through Hormuz down X σ."

**2b — IMF official disruption corroboration + modeled spillovers (new ingest + sidecar).**
- `ingest/disruptions.py` + a Temporal-ingested DuckDB `dim_disruption_event` (from `portwatch_disruptions_database`, **filter `eventtype='OT'`** for the 5 geopolitical/chokepoint events — Hormuz/Red Sea/Panama/US-ports-strike/Key-Bridge — drowned out otherwise by 122 natural-hazard rows) and `dim_disruption_port_edge` (from `disruptions_with_ports`; `distance_km` is an **association radius, not on-berth** — same cyclone tags ports 25–1,709 km, so threshold it).
- Flag enrichment writes `frontend/public/data/disruptions.json` and attaches `flag.official_event` when an event window `[fromdate, COALESCE(todate, today)]` overlaps the flag window **and** matches the entity (chokepoint via a small hand-curated `name→chokepoint` map — `HORMUZ→chokepoint6`, `SUEZ→chokepoint1`, etc.; ports via `port_edge.portid` within ≤300 km).
- **Honesty differentiator:** because the disruption DB is the **same data producer (IMF)** as the flag's underlying series, a matched OT/RED event is stated **without** the Google-News "possibly related" hedge — `official:true`, e.g. *"IMF PortWatch logs an active disruption: HORMUZ-26 (RED), since 2026-03-01"* as **corroboration, not causation**. Kept visually distinct from the hedged news cards. `todate=NULL` → surface as "ongoing" (`COALESCE` in window math).
- Optional `flag.modeled_dependents` from `spillovers_port_level_impact` (226,904-row **static** bilateral matrix, pulled monthly not per-tick): top-N by `relative_capacity_at_risk`, labelled **"IMF modeled structural dependency (static, not event-specific)"** — never summed into a realized-dollar figure (the BUSINESS-PLAN.md first-party $-exposure stays the headline).

**Deliverables.** `business/internal.py` (`run(ctx)`, registered as `internal`); detector second-pass wiring; `ingest/disruptions.py`; DuckDB tables above; `disruptions.json`; sparkline `avg_vessel_size_tons` + `signal_agreement` fields on the per-entity records; frontend `<OfficialEvent>` chip (un-hedged) + `getJson('data/disruptions.json').catch(()=>null)`.

**Definition of Done / receipt.**
- Hormuz flag shows `signal_agreement:"agree"` (count **and** tonnage both flagged) — the receipt that the tonnage pass works.
- Hormuz flag carries `official_event:{eventname:"HORMUZ-26", alertlevel:"RED", ongoing:true, official:true}` matched via the chokepoint name map.
- A natural-hazard-only run (no OT match) leaves `official_event:null` — no false corroboration.
- `avg_vessel_size_tons` renders on the chokepoint sparkline and is **absent/`null`** on near-zero-traffic days (NULLIF guard).

---

## Wave 3 — Weather / storms (free, KEYLESS) → `weather.json`

**Goal.** Attach an active tropical cyclone as a **candidate physical driver** of a port/chokepoint flag when its forecast cone/track overlaps in **space and time** — labelled "possibly related," never "caused."

**Deliverables.**
- `backend/freight_radar/business/weather.py` (`run(ctx)`, mirrors `news.py`): GET **NHC `CurrentStorms.json`** (keyless, verified live, storm "Amanda"; Atlantic/E-Pac/C-Pac only) + **GDACS `geteventlist/SEARCH?eventlist=TC`** (keyless, verified, 24 events; **global** incl. W-Pacific/Indian). Normalize both → one storm list; **dedup** on `(name, ~position within 1°, same day)` preferring NHC's official cone.
- Cone polygons: NHC tropical **MapServer** cone layers `?f=geojson` for NHC storms; **GDACS `getgeometry`** wind-buffer/uncertainty polygon for GDACS-only storms; fall back to "within N nm of track" radius. Persist `match_type ∈ {cone_polygon, track_radius}`. **Simplify** polygons (Douglas-Peucker) to keep the sidecar small / the globe light.
- **Two-gate match (documented in code):** GATE 1 spatial — flag point-in-cone-polygon OR within radius (75 nm ports / 150 nm chokepoints, cone preferred); GATE 2 temporal — flag `as_of` within `[from-1d, to+2d]`. **Both** gates required to emit a block.
- Honest confidence tier (not a causal claim): `observed_overlap` > `forecast_overlap` ("cone is a probability envelope, ~60-70% containment") > `proximity_only`. `relation:"possibly_related"` + fixed disclaimer (exactly `news.py`'s discipline). Drop storms with `advisory` older than ~12h. Per-basin `source_coverage` so "no block" ≠ "no storm" (could be a coverage gap).
- **JTWC is NOT a usable keyless endpoint** (403s automation) — W-Pacific routed via GDACS, stated plainly.
- Frontend: cone/track as a translucent per-flag globe overlay + a "Likely physical driver: <Storm> (cat/TS), cone overlaps, advisory <ADVDATE>" chip; `getJson('data/weather.json').catch(()=>null)`. Manifest gains `weather_storms`/`weather_as_of`.
- Tests: every block has non-null `storm_name` + parseable advisory time + `relation=="possibly_related"` + disclaimer + a confidence tier; out-of-window flag → **no** block (temporal gate); outside-cone-and-radius → **no** block (spatial gate); **Hormuz fixture yields zero blocks** (its cause is geopolitical — regression guard against false causation).

**Definition of Done / receipt.**
- For an active storm (e.g. Amanda) whose cone overlaps a tracked port flag, `weather.json` emits one block with the cone polygon, `confidence`, and disclaimer.
- The **Hormuz flag yields an empty weather block** — the negative-case receipt proving the layer does not manufacture causation.
- Both spatial and temporal gate tests pass (a storm arriving after the anomaly cleared produces no match).

---

## Wave 4 — AIS-computed congestion (free, **NEEDS A FREE KEY**, live-forward only) → `dwell.json`

**Goal.** Replace the honest caveat *"congestion inferred from port calls, not direct dwell-time data"* with a real, source-computed **median anchorage-wait / berth-hours** metric — and corroborate Cape-rounding/slow-steaming. **Deliberately last:** it is the only layer that is *not keyless* and only *live-forward*.

**Key-requirement, stated plainly.** The primary source **aisstream.io is free but NOT keyless** — its `SubscriptionMessage` schema makes `APIKey` mandatory (a free GitHub-login-gated key). With **no `AISSTREAM_API_KEY`, the whole dwell layer simply doesn't appear** (`.catch(()=>null)`), exactly like the existing `ships.json` demo/offline ladder. There is **no free global AIS history**, so dwell builds **forward from first-run day** (`coverage_start_date`) — the single biggest scope limit, stamped on the contract and the UI. AISHub (requires hosting a physical receiver) and NOAA Marine Cadastre (free+keyless but US-EEZ-only, 116 GB) are **rejected as primary**; NOAA is a one-time US-port backfill/validation harness only.

**Deliverables.**
- Extend the **existing** isolated `sidecar/ais_consumer.py` (don't rewrite, don't make it a Temporal activity — its docstring forbids it): keep `ships.json`, add `FilterMessageTypes:[PositionReport, ShipStaticData]` (vessel type), and emit per-vessel geofence-state transitions into an append-only DuckDB `fct_ais_geofence_event`.
- `config/port_geofences.json` — two concentric rings per tracked port (`r_berth_km ~3-5`, `r_anchor_km ~3-25`), **seeded from PortWatch point lat/lon** (PortWatch is **point-only — no berth/anchorage polygons**, verified) and hand-tuned for the top ~20; the rest labelled approximate.
- Per-vessel **state machine** keyed on `(geofence, NavigationalStatus, Sog)`: `approach → anchorage_wait → berth → depart`, with dwell-confirm timers + hysteresis (mirror `lifecycle.py`). **Geometry wins over crew-entered NavigationalStatus** on conflict (it's frequently stale/wrong). Median/p90 only, winsorize (a 600h "berth" is a stuck-MMSI artifact); require `ShipStaticData type=cargo`.
- A **Temporal activity** (durable, like the detectors) reads the append-only events table → DuckDB `fct_port_dwell(portid, date, vessel_class, median_wait_hrs, p90_wait_hrs, median_berth_hrs, n_waiting, n_berthed, coverage_start_date, method)` and writes **per-entity (portid)** `dwell.json`. The non-deterministic socket stays **out** of the workflow; only the aggregation is in Temporal.
- New `port_dwell_spike` detector (z-score on the dwell series via existing `detectors.py`), joining exposure by `portid` like every other flag — labelled "computed from AIS positions; cause not asserted."
- Secondary, clearly "indicative" (terrestrial-AIS mid-ocean gaps under-count): `fct_cape_rounding` (distinct cargo MMSIs crossing a Cape gate/day) **corroborating** — not replacing — the existing `cape_reroute` detector; `fct_slow_steaming` (median laden Sog vs baseline).
- **Caveat swap only where coverage exists:** replace *"Congestion … inferred from … port calls, not … direct vessel dwell-time data"* with *"Median anchorage wait X.Xh vs Y.Yh trailing-30d norm (z=+Z), measured directly from AIS vessel positions since {coverage_start_date}."* Keep the old caveat **verbatim** where `coverage_start_date` is null/after the date — both methods coexist.
- One-time NOAA Marine Cadastre GeoParquet backfill/validation harness (separate dev script, **not** in the Temporal loop) to ground-truth the state machine over a US-port month.
- Tests: every dwell row carries `coverage_start_date` + `method` + `source`; no `port_dwell_spike` flag asserts a cause; demo/offline mode (no key) writes a labelled `mode:"demo"` sidecar.

**Definition of Done / receipt.**
- With a live `AISSTREAM_API_KEY`, after a forward-accumulation run, `dwell.json` shows a real `median_wait_hrs` for at least one tracked port with `mode:"live"` and a `coverage_start_date` — and the feed's caveat for that port has **swapped** to the computed line.
- **Without** the key, `dwell.json` is `mode:"demo"`/absent and the feed shows the original inferred caveat — proving the keyless default degrades honestly.
- A `port_dwell_spike` flag joins to `exposure.json` by `portid` with no new plumbing.

---

## Data contracts

All sidecars: `generated_at` (ISO), loaded with `.catch(()=>null)`, optional block in `useData.js`.

### `market.json` (Wave 1 — per-flag + global indicators)
```jsonc
{
  "generated_at": "ISO", "as_of": "ISO",
  "indicators": {
    "brent":        {"value": 98.1, "unit": "USD/bbl",    "change_pct_1d": -0.4, "change_pct_7d": 4.2, "as_of": "2026-06-02", "source": "FRED DCOILBRENTEU", "source_url": "...", "stale": false},
    "wti":          {"value": 96.3, "unit": "USD/bbl",    "...": "..."},
    "natgas":       {"value": 3.24, "unit": "USD/MMBtu",  "...": "..."},                       // LNG proxy
    "bunker_vlsfo": {"value": 612,  "unit": "USD/mt", "estimate": true, "basis": "modeled_from_brent", "source": "derived; ref Ship & Bunker"},
    "fx_eurusd":    {"value": 1.16, "unit": "USD/EUR",    "...": "..."},
    "fx_usdcny":    {"...": "..."},
    "container_fbx":{"value": 2800, "unit": "USD/FEU", "manual": true, "as_of": "2026-05-28", "source": "Drewry WCI", "attribution": "FBX © Freightos"}  // only if human-entered
  },
  "items": {                                                                                   // per-flag, keyed by flag_id
    "b74be045769441ea": {
      "entity": "Strait of Hormuz",
      "linked": [
        {"instrument": "brent",  "label": "Brent crude",          "value": 98.1, "unit": "USD/bbl",   "change_pct_7d": 4.2, "as_of": "2026-06-02", "source": "FRED DCOILBRENTEU", "source_url": "...", "why": "~20% of seaborne oil transits Hormuz"},
        {"instrument": "natgas", "label": "Natural gas (LNG proxy)", "value": 3.24, "unit": "USD/MMBtu", "...": "..."}
      ],
      "relation": "exposure_context",
      "disclaimer": "Prices shown are what this chokepoint plausibly affects; co-movement is not proof this disruption moved them."
    }
  },
  "notes": ["..."]
}
```

### `disruptions.json` + `flag.official_event` / `flag.modeled_dependents` (Wave 2)
```jsonc
{ "generated_at": "ISO",
  "events": [ {"eventid": 1000000, "eventtype": "OT", "eventname": "HORMUZ-26", "alertlevel": "RED",
               "country": "...", "fromdate": "2026-03-01", "todate": null, "ongoing": true,
               "n_affectedports": 1, "affectedports": ["port..."], "lat": 26.5, "lon": 56.2,
               "official": true, "source": "IMF PortWatch portwatch_disruptions_database"} ] }
```
Attached to each flag (in `flags.json`, un-hedged when non-null):
```jsonc
"official_event":     {"eventid": 1000000, "eventname": "HORMUZ-26", "eventtype": "OT", "alertlevel": "RED",
                       "fromdate": "2026-03-01", "todate": null, "ongoing": true, "match_basis": "chokepoint_name_map"},
"modeled_dependents": [{"to_portid": "port...", "to_portname": "Rotterdam", "to_country": "NL", "relative_capacity_at_risk": 0.12}]  // labelled "IMF modeled structural (static)"
```
Per-entity tonnage/mix fields fold into the existing per-chokepoint records:
```jsonc
{"portid": "chokepoint6", "tonnage_z": -4.1, "tonnage_flagged": true, "count_flagged": true,
 "signal_agreement": "agree", "avg_vessel_size_tons": 41250.0}   // avg_vessel_size_tons null on near-zero-traffic days
```

### `weather.json` (Wave 3 — storms + per-flag matches)
```jsonc
{ "generated_at": "ISO", "as_of": "ISO",
  "sources": ["NOAA NHC CurrentStorms.json + tropical MapServer", "GDACS geteventlist (TC)"],
  "coverage": {"nhc_basins": ["AL","EP","CP"], "global_via": "GDACS"},
  "storms": [ {"storm_id": "ep012026", "name": "Amanda", "basin": "EP", "classification": "TS",
               "intensity_kt": 35, "pressure_mb": 1006, "lat": 10.6, "lon": -128.2,
               "movement_dir_deg": 305, "movement_speed_kt": 8, "advisory_time": "ISO",
               "window": {"from": "ISO", "to": "ISO"}, "source": "NHC", "alert_level": null,
               "cone": { "type": "Polygon", "coordinates": [[...]] }, "track": { "...": "..." } } ],
  "matches": {                                                                                  // per-flag, keyed by flag_id
    "<flag_id>": {"storm_id": "ep012026", "storm_name": "Amanda", "classification": "TS",
                  "relation": "possibly_related", "match_type": "cone_polygon", "distance_nm": null,
                  "confidence": "forecast_overlap", "window_overlap": true,
                  "advisory_time": "ISO", "source": "NOAA NHC, advisory 12 2026-06-03",
                  "disclaimer": "A tropical cyclone overlaps this location in space and time — a plausible physical driver, not a confirmed cause of this anomaly."}
  } }
```

### `dwell.json` (Wave 4 — per-entity by portid)
```jsonc
{ "generated_at": "ISO",
  "source": "aisstream.io terrestrial AIS",
  "method": "per-vessel geofence state machine (approach->anchorage_wait->berth->depart)",
  "mode": "live | demo | offline",
  "coverage_start_date": "2026-06-03 | null",
  "ports": [ {"portid": "port1188", "name": "Shanghai", "lat": 31.19, "lon": 121.64,
              "median_wait_hrs": 18.4, "p90_wait_hrs": 41.2, "median_berth_hrs": 22.1,
              "n_waiting": 12, "n_berthed": 30, "baseline_wait_hrs": 11.0, "wait_z": 2.3, "as_of": "ISO"} ] }
```

### Manifest extension (all waves)
```jsonc
"layers": {"market": {"present": true, "as_of": "ISO", "kb": 4}, "internal": {...}, "weather": {...}, "dwell": {...}},
"weather_storms": 2, "weather_as_of": "ISO"
```

---

## How it stays honest + free

**Each source verified — free, and explicitly flagged where a key or licence applies:**

| Layer | Source | Free? | Keyless? | Honesty handling |
|---|---|---|---|---|
| Market | FRED `fredgraph.csv` | ✅ | ✅ (needs browser UA) | **Public-domain — the licence-safe primary.** 1–2d lag → durable, not freshest. |
| Market | Stooq CSV, Yahoo v8 | ✅ | ✅ (verified live) | Fresh cross-check. **Stooq forbids redistribution without consent / is personal-non-commercial; Yahoo ToS is gray** — cite clearly, keep app portfolio/non-commercial; prefer FRED for the durable layer. |
| Market | FBX / WCI / SCFI / BDI | ✅ to view | ❌ **not keyless JSON** | SCFI login-walled, BDI Baltic-licensed, FBX/WCI attribution-gated HTML → **manual cited weekly values, `manual:true` + attribution, never scraped.** |
| Market | Bunker (VLSFO) | n/a | n/a | Ship & Bunker 403s bots, no API → **`bunker_vlsfo` is `estimate:true`, `basis:"modeled_from_brent"`**, references S&B for humans to check. |
| Internal | ArcGIS `weJ1QsnbMYJlCHdG` (disruptions, edges, spillovers, chokepoints) | ✅ | ✅ (verified live) | Same producer as the flags → OT/RED match is **un-hedged corroboration**. Spillovers labelled **"IMF modeled, structural, static"**; `distance_km` is a radius not a berth-hit. |
| Weather | NHC `CurrentStorms.json` + MapServer, GDACS `geteventlist`/`getgeometry` | ✅ | ✅ (verified live) | **JTWC 403s automation — not usable keyless; W-Pacific via GDACS.** Per-basin `source_coverage` so "no block" ≠ "no storm." |
| AIS | aisstream.io | ✅ | ❌ **needs a free GitHub key** | Stated plainly: no key → labelled `mode:"demo"`/absent. **No free global history → live-forward only**, `coverage_start_date` stamped. |

**Estimates labelled, sources cited + dated.** Every market value carries `source`+`source_url`+`as_of`; modeled/derived numbers (bunker, slow-steaming, spillover dependency) carry `estimate:true`/`"indicative"`/`"IMF modeled"`. Stale series flag `stale:true`. Code owns every number and citation — no LLM invents a price, storm name, or dwell figure (the `news.py` invariant, enforced by per-layer tests).

**Correlation ≠ causation, encoded structurally.** Market and weather emit `relation:"exposure_context"` / `"possibly_related"` + a fixed disclaimer — a Hormuz flag beside a rising Brent print, or a cone over a port, is never rendered as "X caused Y." The Hormuz fixture is a permanent regression guard: it must yield **zero** weather blocks (its cause is geopolitical) and its `official_event` corroboration comes from IMF's own log, not inferred causation. The only un-hedged statement in the whole expansion is the IMF same-producer disruption corroboration, because it's an official event log, not an inference.

**Composes with `BUSINESS-PLAN.md`, doesn't duplicate it.** The first-party $-exposure layer (flags → user trade dataset → realized dollar exposure) remains the **headline number** and is untouched. These four layers are *context around* that number: market = "what prices this lane touches," weather = "a possible physical driver," internal = "official corroboration + structural dependents," dwell = "real operational congestion." The modeled spillover dependents and any freight-rate × exposure deltas are explicitly **never summed into a realized-dollar figure** — that role belongs to BUSINESS-PLAN.md's first-party computation alone.
---

## Wave 5 (capstone) — "Ask Freight Radar" conversational layer

**Goal.** A chat front door over every signal so a user can just ask — *"I source petrochem from the Gulf and electronics from Shanghai, what's my risk?"* — and get a plain-English answer where **every number traces to the data**. The chat gets richer with each layer above (a market move, a storm cause, a dwell read all become askable).

**Two tiers — so it works on the free static demo AND gets smart with a backend.**

**Tier 1 — deterministic grounded Q&A (client-side, $0, works on Pages today).**
An intent router + answer templates over the already-loaded sidecar JSON. Handles the common asks with **no LLM and zero hallucination risk**:
- *"what's going on with &lt;entity&gt;"* → that entity's flag, trend, history, business exposure, news, market/weather/dwell.
- *"what's my biggest risk / exposure"* → rank `exposure.json` + critical flags.
- *"what's getting worse"* → entities trending `deepening`/`intensifying`.
- *"am I exposed to &lt;region/port&gt;"* → match user lanes → flags on that route.
Built as a frontend `Chat.jsx` panel; answers are assembled from the data with citations to the rows. Deterministic, instant, free, deployable on the static site.

**Tier 2 — LLM copilot (backend, for free-form / advanced).**
`backend/freight_radar/api/chat.py`: a `/api/chat` endpoint that (1) **retrieves** the relevant flags/entities/exposure/news/market/weather/dwell context from DuckDB + the sidecars, (2) builds a **grounded** prompt, (3) calls a **pluggable** LLM — **Ollama locally = $0** (default), or Claude API = metered (flagged) — and (4) returns an answer that **cites the data it used**. Same honesty invariant as the news/business layers: *the LLM phrases; every number and citation comes from the retrieved data, never invented*; an explicit "sources" list of the flags/articles used; an honest "I don't have data on that" fallback. Needs the FastAPI backend running (docker/EC2 path), not static Pages.

**Deliverables.**
- `frontend/src/components/Chat.jsx` (Tier 1 always on; Tier 2 used automatically when `/api/chat` is reachable).
- `frontend/src/lib/ask.js` — the deterministic intent router + grounded answer templates over the sidecar data.
- `backend/freight_radar/api/chat.py` — retriever + grounded prompt + pluggable LLM client (Ollama/Claude) + citation assembly; wired into the existing FastAPI app.
- A small intent fixture set; honesty test: **every numeric claim a Tier-1 answer makes must exist in the source JSON**.

**DoD (receipt).** On the static demo, typing *"what's my biggest risk?"* returns Hormuz (−92% persistent collapse, deepening, $65M Gulf exposure) with the real numbers and a link to its card — **no LLM**. With the backend + Ollama up, *"should I reroute my Suez shipments?"* returns a grounded, cited answer drawn only from the data. The honesty test passes: no Tier-1 numeric claim is absent from the source JSON.

---

## How this composes with the existing plans

- **BUSINESS-PLAN.md** (first-party $-exposure depth) is untouched — its B-waves and these data-layer waves are independent; the chat capstone reads both.
- Build order by value-per-effort: **Wave 0 (refactor — fixes the orphaned-enricher bug)** → **Wave 1 (market, free+verified)** → **Wave 2 (internal signals, zero new deps)** → **Wave 3 (weather, free)** → **Wave 4 (AIS dwell, needs a free key)** → **Wave 5 (chat capstone)**.
