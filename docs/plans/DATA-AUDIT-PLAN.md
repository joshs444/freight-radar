# Freight Radar — Data-Audit Implementation Plan

_Turns the verified [data audit](#) (16 findings, adversarially re-verified, 0 rejected) into a sequenced, file-level build plan. The headline: the warehouse already holds far more than the app reads — three populated per-cargo-type dimensions go to zero consumers, and detection runs entirely on blended counts. This plan uses what we have first, then adds the new free/keyless sources and hardens the ETL._

## Status — shipped 2026-06-04 (build order A → D → B → C)

- **Phase A — cargo-aware detection — ✅ shipped + live.** A1 per-entity cargo-mix (snapshot `cargo_mix`, the CargoMix card); A2 dominant-cargo-type port detector (`port_cargo_type_drop/_spike` — surfaced Hong Kong/Kaohsiung/Port Klang container drops the blended detector missed); A3 avg-vessel-size chokepoint detector (`chokepoint_vessel_size_shift`, capacity÷count, orthogonal to count — caught Yucatan Channel +34%). Labels honest (avg size ≠ utilization; attribution, never "total steady").
- **Phase D — ETL hardening — ✅ shipped + prod-verified.** D1 non-retryable join-coverage gate in the Temporal path; D2 silent-column-drop guard in both ingest frames; D3 fetch-completeness (`verify_count`, the formerly-dead `count()`). Verified end-to-end by dispatching `refresh.yml` (full backfill ran the guards with no false-raise). _D4 (optional provenance) not done — left as optional._
- **Phase B — national-dependence weighting — ✅ shipped + live.** Ingested `share_country_maritime_*` + per-type `vessel_count_*`; port severity now blends national dependence (a sole gateway like Mombasa ≈ 99.8 % outranks an equal-sized peer); flag briefs carry the dependence line; a National-dependence chip renders the import/export share.
- **Phase C1 — live storm layer — ✅ shipped + live.** `weather.py` (NHC CurrentStorms + GDACS active TCs, NOAA-dup dedup, server-side for CORS) → `weather.json`; storm chip on flags within 500 km. Silent off-season (honest dormant state).
- **Phase C2 — GDELT attention — ❌ cut.** GDELT's free DOC 2.0 endpoint hard-rate-limits a single IP (429 even 180 s cold after a small burst), and the weekly `refresh.yml` runs from GitHub's *shared* CI IP — so attention would be permanently empty in prod while adding ~33 s of doomed calls per refresh. Shipping a never-populated, pipeline-polluting layer fails the honesty bar, so it was backed out cleanly. Revisit only with a paid/keyed attention source.

## Guiding principles

1. **Additive, not destructive.** New detectors fire as *new flag kinds* alongside the existing blended detection — never replace `n_total`/`portcalls_total` flags, so existing behavior stays stable while we add resolution.
2. **Honesty holds.** Every new number computed from real source columns; labels stay precise (avg-vessel-size is "avg cargo tonnage per vessel," **not** utilization; storm cones are "possibly related," GDELT is "attention, not causation"). The chat-grounding and JS↔Python parity tests stay green at every step.
3. **Deploy each phase.** Every phase ends committed + pushed + verified live, with the re-detection cascade (exposure/news/stress/brief/world all re-run off new flags) checked, not assumed.
4. **Data prerequisites are explicit.** Detection-only changes need no re-ingest (the columns are already populated). Dimension changes need a re-backfill — called out where required.

---

## Phase A — Cargo-aware detection (the "use what we have" headline)

_No re-ingest: `fct_port_daily` (18 per-type cols) and `fct_chokepoint_daily` (per-type `n_*` + `capacity_*`) are already fully populated. Pure read-side + new detectors._

### A1 — Surface per-port / per-chokepoint cargo-mix (display, zero risk)
- **`export_snapshot.py`** `_ports()` / `_chokepoints()`: add the per-type split (`import_container/tanker/dry_bulk/…`, `portcalls_*`; chokepoint `n_container/tanker/dry_bulk/roro/general_cargo` + `capacity_*`) to each record.
- **Frontend** `DataFeed.jsx` row detail: a small "cargo mix" block (container / tanker / dry-bulk / RoRo / general split, % of total) for the selected entity.
- **Test:** snapshot row carries the per-type fields and they sum to the total.

### A2 — Dominant-cargo-type port detector (additive)
- **`detect/run_detection.py`**: in addition to the blended `portcalls_total` detector, run `detect_series` on the port's **dominant** cargo type (the type with the largest share). Emit a new kind `port_cargo_type_drop`/`_spike` carrying `{cargo_type, share, value, baseline, pct}` so a brief reads "Shanghai **container** imports −18%, tanker flat" instead of a blended total.
- Guard: only fire when the dominant type is a meaningful share (≥ ~40%) and the type-specific z clears the same gate as the blended detector (no new false-positive surface).
- **Brief** (`export_snapshot`/detector brief text): include the cargo-type qualifier + the non-moving types for contrast.
- **Tests:** fires on a synthetic container-only drop while the blended total stays flat; does **not** fire when the move is evenly spread across types.

### A3 — Avg-vessel-size / tonnage detector for chokepoints (additive, new axis)
- **`detect/run_detection.py`** (or a small `detect/tonnage.py`): per chokepoint, build `avg_vessel_size = capacity_total / NULLIF(n_total,0)` and run the existing `detectors.py detect_series` (STL + rolling-z) on it. Emit `chokepoint_vessel_size_shift`. Audit receipt: at Gibraltar this series correlates **−0.08** with the count (genuinely orthogonal) and moved >2σ on 11 days the count detector couldn't see.
- Also expose transiting **tonnage** (`capacity_total`) trend alongside the count on the chokepoint card, so a tanker-heavy disruption (Hormuz ≈ all tanker) reads in tonnes, not just vessels.
- Label precisely: "avg cargo size of transiting vessels (tonnage ÷ vessels)" — **never** utilization (capacity is a flow, not a ceiling — audit-confirmed; do **not** build an `n/capacity` %).
- **Tests:** fires on a size shift with flat count; `NULLIF` guard on zero-traffic days.

### A4 — (stretch) Vessel-class-share divergence at chokepoints
- z-score on `tanker_share`/`container_share` (`n_class/n_total`), firing when a class diverges from its 28-day norm while `n_total` is steady — energy-specific signal at Hormuz/Bab/Suez. Additive kind `chokepoint_class_shift`. Defer if Phase A is already large.

**Cascade check (all of Phase A):** new flags flow through `enrich.py` → exposure/news/hazards/stress/world/brief. Re-run the full publish, confirm the new flag kinds render, existing flags are unchanged, and the brief/chat narrate the cargo detail. Re-run `pytest -m "not live"`, `npm run test:chat`, `npm run test:parity`.

---

## Phase B — National-dependence weighting (needs a re-backfill)

_The reference layers expose a free IMF systemic-importance score we drop at the config boundary._

### B1 — Ingest the dropped reference fields
- **`config.py`** `DIM_OUT_FIELDS`: add `share_country_maritime_import,share_country_maritime_export` and the 5 per-type `vessel_count_*`.
- **`ingest/dims.py`** `_DIM_MAP`: map the new fields.
- **`storage/schema.sql`**: add the columns to `dim_port` / `dim_chokepoint`.
- **Data prerequisite:** a **re-backfill** repopulates the dims (`python -m freight_radar.backfill`, or just let `refresh.yml` rebuild). The committed DB is gitignored and the cron rebuilds it fresh, so the next run picks it up; for local dev, re-backfill once.
- **Test:** dims expose the new columns and they're populated (mirror the existing lat/lon presence guard).

### B2 — Use it
- **`detect/run_detection.py`** `_econ_weights`: blend `share_country_maritime_*` into severity weighting so a port carrying 60% of a country's trade outranks one at 3% (currently weighted by blended `vessel_count_total` alone).
- **Frontend / brief:** "Port X handles **N%** of {country}'s maritime imports" on the flag — a concrete systemic-importance line. (Receipts: Mombasa = 99.84% of Kenya's imports; sole-port countries = 100%.)
- Per-type `vessel_count_*` powers a static "this port is ~80% container" profile chip.

---

## Phase C — New free + keyless external layers

### C1 — Live storm forecast cones (NHC + GDACS) → `weather.py` → `weather.json`
- New enricher mirroring `hazards.py`: fetch **NHC** `CurrentStorms.json` (Atlantic/E-Pac/C-Pac) **and** **GDACS** `geteventlist/SEARCH?eventlist=TC` (W-Pac/Indian-Ocean basins NHC omits — exactly the Malacca/Hormuz/Taiwan/Korea/Luzon chokepoints). Normalize + dedup on `(name, ~1° position, same day)` preferring NHC's official cone; use GDACS `getgeometry` for the wind-buffer polygon on GDACS-only storms.
- Match active-storm cone vs flagged ports/chokepoints in **space + time**; attach as a "possibly related" physical driver (never "caused"). Distinct from the existing historical/curated GDACS-via-PortWatch `hazards` layer (which has no live cone).
- **Frontend:** a live-storm chip on affected flags + (stretch) a cone overlay on the globe.
- **Honesty + resilience:** label as live NWS/GDACS forecast; degrade to null on fetch failure (the `.catch` enricher pattern). **Tests:** cone↔chokepoint spatial+temporal match with fixtures, no network.
- Note: this is the already-designed `DATA-LAYERS-PLAN.md` Wave 3 — registers as one line in `enrich.py`.

### C2 — GDELT attention trend → per-flag `attention`
- New enricher: for each active flag (only ~6), query GDELT DOC 2.0 `timelinevol` **serially, ≥5s apart** (hard rate limit — handle 429 by spacing, degrade to null). Attach a 7–30d attention sparkline + an "attention z-score" alongside the existing Google-News headlines.
- Strictly **soft corroboration** ("attention rising"), never causation.
- **Test:** parse the `timeline` JSON shape from a fixture; z-score math.

---

## Phase D — ETL hardening (correctness guards)

_All small; each turns a silent failure into a loud one. Tests so they never break the weekly cron._

- **D1 — Join-coverage gate in the durable path.** `temporal/activities.py` `fetch_portwatch`: after `cov = join_coverage(...)`, raise a **non-retryable** `temporalio.exceptions.ApplicationError` when `cov < MIN_JOIN_COVERAGE` (the CLI already does this; the durable path only logs). _Note: production today runs via `refresh.yml`→`backfill` which already gates — this closes the latent Temporal-path hole._
- **D2 — Silent-column-drop assertion.** `ingest/portwatch.py` `_to_frame` + `ingest/dims.py`: after building `keep`, assert every non-optional mapped source key was present (raise on absence), mirroring the existing lat/lon guard — so a renamed PortWatch field fails loudly instead of landing all-NULL (reproduced in the audit).
- **D3 — Fetch-completeness check.** Call the (currently dead) `ArcGISClient.count()` once per layer after `query_date_window` and assert `len(rows) == server_count` — turns a silently dropped page into a hard failure.
- **D4 — (optional) Production provenance.** Add a final step to the publish/refresh that writes `meta_ingest_runs` + `update_source_status` with real `max(date)` + `status='stale'` when data lags — or drop the meta tables to close the honesty gap they currently imply.

---

## Sequencing & rationale

| Phase | What | Re-ingest? | Risk | Value |
|---|---|---|---|---|
| **A** | Cargo-aware detection (mix display + dominant-type + avg-vessel-size) | No | Med (detection cascade) | **Highest** — the "use what we have" headline |
| **B** | National-dependence weighting | **Yes (backfill)** | Low–Med | High — systemic-importance signal |
| **C** | Live storm cones + GDELT attention | No | Low (additive sidecars) | Med–High |
| **D** | ETL guards | No | Low | Correctness/credibility |

**Order:** A → D → B → C. Rationale: **A** is the biggest, no-ingest, highest-value win; do it first while context is fresh. **D** is cheap correctness that protects the cron before we add re-ingest churn. **B** needs a backfill, so batch it after the guards are in. **C** is purely additive and can slot last (or in parallel — independent sidecars). Each phase deploys + verifies live independently.

**Definition of done (every phase):** built · `pytest -m "not live"` + `test:chat` + `test:parity` green · re-detection cascade verified · headless screenshot, 0 console errors · committed (no AI trailer) · pushed · **live receipt confirmed** (poll the CDN past the deploy lag).
