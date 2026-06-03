# Freight Radar

**A living dark-globe of ocean freight where the world's maritime chokepoints glow by real daily activity, and a durable agent auto-flags disruptions — congestion spikes, transit collapses, Cape-of-Good-Hope reroutes — into a severity-ranked "current issues" board.**

Every number traces back to source. Nothing is hand-waved.

![Freight Radar — the live globe](docs/hero.png)

---

## What it is

The world's seaborne trade funnels through ~28 maritime chokepoints (Suez, Hormuz, Malacca, Panama, the Taiwan Strait…). When one seizes up, the shock ripples through supply chains weeks before it shows up in the financial press. Freight Radar watches all of them — plus ~2,000 ports — on a 3D globe, runs real change-point detection over the history, and surfaces only the disruptions that clear a statistical bar.

It's built on free, public **IMF PortWatch** data and a durable **Temporal** workflow, and it's scrupulous about saying only what the data supports.

| The whoa frame | A real detected flag | Replay the collapse |
|---|---|---|
| ![globe](docs/hero.png) | ![flag detail](docs/flag-detail.png) | ![time scrubber](docs/timescrubber.png) |

- **Glowing globe** — MapLibre v5 native globe + deck.gl (interleaved) renders 28 chokepoints (amber) and ~2,065 ports (cyan) sized by real vessel activity, with great-circle lane arcs and an atmospheric rim.
- **Current Issues rail** — severity-ranked, auto-flagged anomalies. Click one → the globe flies to it and a plain-English brief expands with the *real* numbers ("Shanghai port calls fell to 18 on 2026-05-25, 79% below its 28-day norm, z = −7.1").
- **Time-scrubber** — replay the trailing 120 days; chokepoint glow dims/brightens by each day's real count and a flag pulses on the actual date it was detected.
- **Durable agent** — a Temporal workflow on a Schedule fetches → detects → attributes → publishes, crash-durably, forever.

---

## How it stays honest

This is the part that matters, and it's enforced in the **UI**, not just the README:

- **Never called "live."** PortWatch is **daily-granularity, refreshed weekly** by the IMF. Every tile shows its source and the data's own `as of <date>`. The value here is the auto-flagging + attribution, not refresh speed.
- **Numbers are computed in Python, from source.** The briefs are template-first with values string-substituted from real calculations. An optional local-LLM polish layer is gated to *new* flags only and is structurally forbidden from inventing a number.
- **High precision over a busy rail.** A change-point gate (STL residual → rolling z **AND** CUSUM **AND** a `ruptures` PELT breakpoint within 7 days) suppresses one-day blips. On the current data it cuts 13 raw z-detections down to **4 gate-confirmed** anomalies — and shows the rest winding down through an explicit **lifecycle** (`new → ongoing → escalated → resolved`).
- **The Cape-reroute detector doesn't cry wolf.** It only fires on a real Red-Sea-down / Cape-up divergence. On the current window (Red Sea +6.3%, Cape +0.9%) there is no divergence, so **it honestly does not fire** — and says so.
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
| Frontend | React + Vite, **MapLibre GL v5 globe**, **deck.gl v9** via `MapboxOverlay(interleaved)`, token-free CARTO dark basemap |
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

pytest -m "not live"     # 17 deterministic tests
pytest -m live           # + the live PortWatch contract tests (network)
```

### Frontend
```bash
cd frontend
npm install
npm run dev      # http://localhost:5173
npm run build    # static bundle -> dist/  (deploy anywhere)
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
- **Durable loop** — the workflow runs end-to-end on Temporal's in-process test server; a 2nd identical run makes **zero** attribution calls (dedup ledger); RetryPolicy re-drives a transient failure.
- **Frontend** — headless-Chrome screenshots confirm the globe renders (WebGL2 + interleaved deck.gl), flags are clickable (fly-to + real brief), and the scrubber replays real history.
- **17/17** non-live backend tests pass.

Data: [IMF PortWatch](https://portwatch.imf.org/) (CC BY 4.0). Basemap © OpenStreetMap © CARTO.

See [`PLAN.md`](PLAN.md) for the full wave-by-wave build plan and the verified data contracts.
