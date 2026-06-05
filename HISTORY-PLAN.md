# Freight Radar — "Play Through History" mode (2019 → today)

_A History view that animates the global ocean-freight stress index across PortWatch's
full daily record (verified **2019-01-01 → present**, ~2,700 days), so you can watch the
real shocks land — COVID (spring 2020), the Ever Given blocking Suez (Mar 2021), the
Panama drought (2023), the Red Sea / Houthi crisis (late 2023→) — with dated, cited event
captions. 2015 isn't available (PortWatch starts 2019); this window covers every major
disruption since._

## Principles (unchanged from the rest of the app)

- **Honesty first.** Every number is computed in Python from PortWatch daily transits; the
  stress index stays labeled as our own composite (breadth+depth); event captions are
  curated + source-cited, never generated. The view labels itself "daily transits since
  2019 · index is our composite · events curated".
- **Free / keyless.** Same PortWatch ArcGIS source already in use; no new services.
- **Scope = the 28 chokepoints + the index.** 28 × 2,700 days is a tiny sidecar; all 2,065
  ports daily (~5M points) is too heavy and isn't the story — the chokepoints are.
- **Reuse, don't rebuild.** The app already has a time-scrubber, a scrub-replay globe, the
  stress index, and an event ledger. History extends those, it doesn't fork them.
- Strict TS + the lint/typecheck/format CI gate apply; deploy + verify live; no AI trailer.

## Phase 1 — Backend: the historical pipeline → `history.json`

- [ ] **1a. Full-range chokepoint pull.** A `history` path that loads the full
  2019-01-01→today daily chokepoint series from PortWatch into DuckDB (the ArcGIS client
  already chunks by date window + verify_count; ~28 rows/day). Ports stay current-snapshot.
- [ ] **1b. Seasonal baseline + daily stress series.** Mirror the live stress formula
  (`narrative/`), but with a STABLE seasonal baseline per chokepoint (a robust day-of-year
  climatology / long rolling median) so a *sustained* shock (COVID plateau) stays elevated,
  not just rate-of-change spikes. Emit a daily stress index 0–100 across the full range +
  each chokepoint's daily deviation-vs-normal.
- [ ] **1c. Curated events.** `config/historical_events.yaml` — dated (point or range),
  titled, blurbed, source-cited disruptions: COVID, Ever Given, 2021–22 congestion, Panama
  drought, Red Sea/Houthi, Hormuz tensions, etc. Each maps to the timeline.
- [ ] **1d. Emit `history.json`** (compact, rounded): `{ range, dates[], stress[],
  chokepoints:[{portid,name,lat,lon,values[]}], events:[{date|from/to,title,blurb,source,url}] }`.
  Lazy-loaded by the frontend only when History opens.
- [ ] **1e. Register** in the enricher/publish path so the weekly refresh keeps it current
  (incremental tail-append; the deep history is stable).
- [ ] **DoD:** `python -m freight_radar.<history>` writes history.json; stress array spikes
  visibly at COVID/Suez/Red Sea (sanity-check the values); `pytest -m "not live"` green.

## Phase 2 — Frontend: the History view

- [ ] **2a. A "History" toggle** by the live controls (the normal app stays clean; History
  is opt-in). Lazy-loads `history.json` + the lib.
- [ ] **2b. Long-range timeline + Play.** A full 2019→today track with a Play/pause that
  sweeps the playhead (≈ a month/second, adjustable), event tick-marks along it.
- [ ] **2c. Drive the scene from the playhead:** the stress **gauge** + a full-range stress
  **sparkline** (playhead riding the line) animate; the **globe** chokepoints recolor by
  their deviation at that date (reuse the existing scrub-replay path).
- [ ] **2d. Event captions.** As the playhead reaches a curated event, a cited caption card
  appears ("Mar 2021 — Ever Given blocks Suez; transits −X%"), source-linked.
- [ ] **2e. Honesty labels** on the view; respects `prefers-reduced-motion` (no auto-play).
- [ ] **DoD:** typed (.tsx, no `any`), lint+typecheck+format clean; headless: Play sweeps,
  stress animates + spikes at the known events, captions show, 0 console errors.

## Phase 3 — Verify + deploy

- [ ] Headless end-to-end (the full play-through, event captions, globe recolor, gauge);
  build + chat + parity green; deploy; **live receipt** past the CDN lag; a quick screenshot
  reel of the COVID + Ever Given + Red Sea moments.

**Order 1 → 2 → 3.** Phase 1 (the honest data) is the foundation and is built/sanity-checked
before any UI. Resume after a compact by re-reading this file + `git log`.
