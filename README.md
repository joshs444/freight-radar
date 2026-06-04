# Freight Radar

**A clean, filterable monitor of ocean freight: a light 3D globe where maritime chokepoints are sized by real daily activity, beside a live disruptions feed where a statistical detection engine auto-flags congestion spikes, transit collapses, and Cape-of-Good-Hope reroutes — filterable to All / Critical / Chokepoints / Ports. Topped by a Global Ocean Freight Stress Index, a deterministic weekly brief, and a grounded "Ask Freight Radar" chat.**

Every number traces back to source. Nothing is hand-waved — the stress index decomposes into its parts, the brief's figures are computed in Python (never by a model), and the chat will only state a number it can cite to a source file.

![Freight Radar — the live globe](docs/hero.png)

---

## What it is

The world's seaborne trade funnels through ~28 maritime chokepoints (Suez, Hormuz, Malacca, Panama, the Taiwan Strait…). When one seizes up, the shock ripples through supply chains weeks before it shows up in the financial press. Freight Radar watches all of them — plus ~2,000 ports — on a 3D globe, runs real change-point detection over the history, and surfaces only the disruptions that clear a statistical bar.

It's built on free, public **IMF PortWatch** data and a durable **Temporal** workflow, and it's scrupulous about saying only what the data supports.

| The whoa frame | A real detected flag | Replay the collapse |
|---|---|---|
| ![globe](docs/hero.png) | ![flag detail](docs/flag-detail.png) | ![time scrubber](docs/timescrubber.png) |

- **Light globe** — MapLibre v5 native globe + deck.gl (interleaved) renders 28 chokepoints as crisp amber marks and ~2,065 ports as faint dust, sized by real vessel activity, with great-circle lane arcs.
- **Filterable monitor feed** — every monitored chokepoint + flagged port, filterable to **All / Critical / Chokepoints / Ports**, sorted critical-first then by real traffic. Click any row → the globe flies to it and a plain-English brief expands with the *real* numbers ("Shanghai port calls fell to 18 on 2026-05-25, 79% below its 28-day norm, z = −7.1").
- **Global Ocean Freight Stress Index (0–100)** — one at-a-glance number in the top bar, with a 30-day sparkline and week-over-week momentum. It **blends breadth** (an economic-weighted mean of every chokepoint's deviation from its normal throughput) **with depth** (the single worst chokepoint), so a concentrated crisis at one strategic strait isn't averaged away. Both components are exposed for inspection.
- **"This week" brief** — a deterministic hero card that assembles 3–6 plain-English, fully-cited bullets from the sidecars at publish time. The figures are string-substituted from real computations; the prose is a template, so no statistic can be hallucinated.
- **Ask Freight Radar** — a grounded chat that runs **entirely in the browser** over the loaded data (no backend, no API key). It answers "what's going on with Hormuz / what's the biggest risk / am I exposed / why does oil matter / how many ships are out today / any storms near a port" — and **only ever states a number it can trace to a source file** (enforced by a test).
- **World Today ribbon** — a global pulse across the top: ships in transit, port calls, and cargo delivered/shipped per day, each with a today-vs-last-week trend + sparkline. Real daily sums from the DB.
- **Natural hazards / official events** — IMF PortWatch (**GDACS**) cyclone/flood/earthquake alerts that hit monitored ports, matched by exact port ID, with flag corroboration when contemporaneous and the GDACS magnitude (e.g. "max wind 213 km/h") shown.
- **Panama Canal leading indicator** — the **ACP**'s own Gatun Lake level + projected max-draft CSVs (free, keyless). Lake level drives the transit draft, so a draft cut shows up here *weeks before* the PortWatch transit count falls — a signal the count data structurally can't provide.
- **Business exposure** — point a trade CSV (LOCODEs or port names, region column optional) and each disruption maps to *your* lanes with a banded **Cost-of-Disruption stack** (carrying cost + reroute premium), coverage reporting, and a "show your work" method panel.
- **Time-scrubber** — replay the trailing 120 days; chokepoint glow dims/brightens by each day's real count and a flag pulses on the actual date it was detected.
- **Self-refreshing in production** — a scheduled **GitHub Action** (`refresh.yml`, weekly + on-demand) rebuilds the DuckDB from PortWatch, re-runs detection + every enricher, and commits the changed sidecars; that push auto-deploys. So the live site stays current without anyone running anything by hand.
- **Durable loop (verified in a test harness)** — the same fetch → detect → attribute → enrich → publish steps are wrapped in a **Temporal** workflow + Schedule, with durability proven end-to-end on Temporal's time-skipping test server (kill the worker mid-run, it re-drives from the last completed activity). The scheduled Action above is the always-on production driver of those identical `publish_static` steps.

---

## How it stays honest

This is the part that matters, and it's enforced in the **UI**, not just the README:

- **Never called "live."** PortWatch is **daily-granularity, refreshed weekly** by the IMF. Every tile shows its source and the data's own `as of <date>`. The value here is the auto-flagging + attribution, not refresh speed.
- **Numbers are computed in Python, from source — the prose is deterministic-template.** Every brief, every flag, and the weekly digest are templates with values string-substituted from real calculations. **No model is in the number path**, so nothing can be hallucinated. (There is a stub seam for optional local-LLM *wording* polish on new flags, structurally forbidden from touching a figure — but production prose is template-only, and that's the point, not a limitation.)
- **The chat states nothing it can't cite.** "Ask Freight Radar" runs client-side over the loaded sidecars; each answer records the raw values it used and the source file each came from. A node test (`npm run test:chat`) runs the engine over a battery of questions and **fails if any cited fact isn't found in its source sidecar** — 100+ facts checked, 0 ungrounded.
- **The stress index is decomposable, not a black box.** Its method string, its `breadth` and `depth` components, and the per-chokepoint contributors all ship in `stress.json`; deviation is measured vs each chokepoint's *normal* (80th-pct of 120 days), so a sustained level-shift the rolling baseline has adapted to still reads as stressed — the same Strait-of-Hormuz lesson the detector learned.
- **High precision over a busy rail.** A change-point gate (STL residual → rolling z **AND** CUSUM **AND** a `ruptures` PELT breakpoint within 7 days) suppresses one-day blips. On the current data it cuts 13 raw z-detections down to **4 gate-confirmed** anomalies — and shows the rest winding down through an explicit **lifecycle** (`new → ongoing → escalated → resolved`).
- **The Cape-reroute detector doesn't cry wolf.** It only fires on a real Red-Sea-down / Cape-up divergence. On the current window (Red Sea +6.3%, Cape +0.9%) there is no divergence, so **it honestly does not fire** — and says so.
- **Official corroboration, dated — never a false cause.** A natural-hazard layer pulls **IMF PortWatch / GDACS** official events (tropical cyclones, floods, earthquakes) that hit monitored ports (matched by the exact port IDs GDACS lists) or chokepoints (by proximity). A flag is only corroborated by a hazard that is genuinely *contemporaneous* (±30 days). Today's flags are geopolitical/congestion with **no** weather overlap — and the UI says so, showing the hazard events with their own dates rather than implying they're live.
- **Garnish is labelled as garnish.** The animated ship trails come from an *optional* AIS sidecar that the flag engine never reads. The legend chip says `live`, `simulated`, or `offline` truthfully; killing the socket changes nothing on the map and no number moves.
- **Holiday-aware.** Benign seasonal dips (Lunar New Year, Christmas, Golden Week) are suppressed so the rail doesn't call a holiday a crisis.

---

## The one architectural seam

The app reads from **local DuckDB tables only** — never from any upstream directly.

```
IMF PortWatch (ArcGIS REST)                 aisstream.io (WebSocket)
        │  reliable backbone                        │  optional garnish
        ▼                                           ▼
   ingest + detect ──► DuckDB ──► publish ──► static JSON ──► React globe
        │              (the only        (snapshot / flags /        ▲
        │               source of        timeseries / manifest)    │
   Temporal workflow    truth)                                FastAPI (live path)
   on a Schedule
```

- **Tier 1 — reliable backbone (load-bearing):** IMF PortWatch. All flags + severity are computed off this tier.
- **Tier 2 — live garnish (non-load-bearing):** aisstream ship trails, write-only to a file the flag engine ignores; degrades to an "offline" badge.

---

## Stack

| Layer | Choice |
|---|---|
| Ingest | Python 3.12, `httpx` async, verified ArcGIS queries with `resultOffset` pagination |
| Storage / detection substrate | **DuckDB** (single file; window functions for rolling baselines) |
| Detection | `statsmodels` STL(7, robust) → rolling z-score, CUSUM, `ruptures` PELT change-point gate; config-driven YAML |
| Orchestration | **Temporal** (`temporalio`) — one durable workflow, 5 activities, RetryPolicy, a Schedule, a dedup ledger |
| API | FastAPI read-only (`/snapshot` `/flags` `/lanes` `/manifest` `/health`) with ETags |
| Frontend | React + Vite, **MapLibre GL v5 globe**, **deck.gl v9** via `MapboxOverlay(interleaved)`, token-free CARTO light basemap; filterable Monitor feed (flags · exposure · market · news · sparklines/trend), top-bar **stress gauge**, "this week" **brief** card, and a client-side grounded **chat** |
| Narrative | Stress index + event ledger + weekly brief computed at publish time (`narrative/`), registered in the same enricher registry as every other sidecar |
| Deploy | docker-compose (temporal · worker · schedule-init · api · frontend); frontend also runs free/static |

---

## Run it

### Backend
```bash
cd backend
uv venv --python 3.12 .venv && source .venv/bin/activate
uv pip install -e .

python -m freight_radar.backfill            # 180-day PortWatch backfill -> data/freight_radar.duckdb
python -m freight_radar.publish             # detect + snapshot + manifest -> frontend/public/data/
python -m freight_radar.export_timeseries   # the scrubber's per-day series
python -m freight_radar.sidecar.ais_consumer --demo   # optional simulated ship trails

pytest -m "not live"     # 41 deterministic tests (detection, temporal, narrative…)
pytest -m live           # + the live PortWatch contract tests (network)
```

### Frontend
```bash
cd frontend
npm install
npm run dev          # http://localhost:5173
npm run build        # static bundle -> dist/  (deploy anywhere)
npm run test:chat    # honesty test: every chat fact must trace to a source sidecar
```

### Full durable loop (Docker)
```bash
docker compose up   # temporal (persistent) + worker + schedule-init + api + frontend
# Temporal Web UI: http://localhost:8233 · app: http://localhost:8080 · api: http://localhost:8000
```
Kill the worker mid-run and restart it — Temporal re-drives the in-flight workflow from its last completed activity. That durability is the point.

---

## Verification (receipts, not assertions)

- **Data plumbing** — 180-day backfill = 4,984 chokepoint + 363,440 port daily rows; `portid`→geometry join 1.00; live contract test green; idempotent re-pull adds 0 rows, 0 PK duplicates.
- **Detection** — flag numbers spot-checked against the raw DuckDB (Shanghai 18 vs 85.96, Hong Kong 30 vs 41.64…); 11 detector tests incl. *fires on a real collapse, not on weekly seasonality*, *PELT gate suppresses spurious spikes*, *Cape fires on divergence / quiet when parallel*, *holiday suppresses a benign dip*.
- **Durable loop** — the workflow runs end-to-end on Temporal's in-process time-skipping test server; a 2nd identical run makes **zero** attribution calls (dedup ledger); RetryPolicy re-drives a transient failure. (Production regenerates sidecars via the same `publish_static` steps; the Temporal path is the always-on orchestration of those identical steps.)
- **Narrative layer** — the stress index reads `calm` on an all-normal system and `high` when a single strategic strait collapses (the depth term isn't averaged away); a sustained level-shift still scores stressed at the latest day; the event ledger diffs appeared/escalated/resolved across runs; and the brief is verified to **never state a number the stress index contradicts** (the stale-flag trap).
- **Grounded chat** — `npm run test:chat` runs the engine over 20+ questions and asserts **every cited fact exists in its source sidecar** (100+ facts, 0 ungrounded).
- **Frontend** — headless-Chrome screenshots confirm the globe renders (WebGL2 + interleaved deck.gl), the stress gauge + "this week" brief render, the chat answers with citations, flags are clickable (fly-to + real brief), and the scrubber replays real history — all with **0 console errors**.
- **Business depth** — a real-world CSV (LOCODEs, alternate spellings, no region column) resolves instead of silently zeroing; coverage is reported ("X of N lanes modeled"); the cost-of-disruption stack's total is exactly carrying + reroute premium (no fabricated lines), with working capital held separate (locked ≠ lost) and a "show your work" method panel.
- **Hazard corroboration** — synthetic GDACS events prove the matcher: exact port-ID matches + chokepoint proximity, old/non-infra events dropped, and a flag is corroborated **only** by a contemporaneous (±30d) hazard — never a stale one (no false causation).
- **41/41** non-live backend tests pass.

Data: [IMF PortWatch](https://portwatch.imf.org/) (CC BY 4.0). Basemap © OpenStreetMap © CARTO.

See [`PLAN.md`](PLAN.md) for the full wave-by-wave build plan and the verified data contracts.
