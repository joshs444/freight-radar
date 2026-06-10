# Hardening plan — fix everything the adversarial review found, at the root

**Status: IN PROGRESS — Wave 0 executing (started 2026-06-09).**
Statuses in this file are kept true as waves land (that discipline is itself item H0-F).

Source: a 37-agent adversarial review (18 dimensions — vision, docs, world model,
detection, honesty, data sources, data architecture, dbt, backend, API/contracts,
ops, UX, frontend, provenance UX, testing/CI, security, screening, completeness
critic). 104 findings; every critical/major finding was independently re-verified
against the code before landing here — none were refuted.

## The root causes (fix these, not just the symptoms)

1. **Receipts are hand-maintained, so they rot.** README counts, plan statuses,
   and "current data" examples were written once and drifted. Fix: receipts are
   dated or machine-checked; a stale receipt fails a test.
2. **The system has no durable memory of its own outputs.** The weekly
   from-scratch DB rebuild silently killed flag lifecycle, blocks any backtest,
   and makes "what did we know last week" unanswerable. Fix: committed
   append-only state, like `events_state.json` already proved out.
3. **Claims and code have no parity gate between them.** ADR-0002/0005 drifted,
   the "AI briefing" is templates stamped as Claude, CUSUM documents a power it
   can't fire, hardcoded lanes sit in the measured tier. Fix: correct every
   claim to match reality, and where cheap, gate it.
4. **String-typed entity coupling.** The Cape-reroute flag's descriptive entity
   string silently matches nothing downstream → zero exposure. Fix: structured
   chokepoint references on flags.
5. **Window myopia.** A 120-day normal forgets sustained disruptions; the cape
   detector only sees transitions; ports never got the persistent pass. Fix:
   long-anchored normals + persistent detection everywhere.
6. **Weekly snapshots presented as live.** Stale `as_of` stamps, no max-age
   demotion, "current" storm positions up to 7 days old. Fix: honest stamps,
   age gates, a daily context refresh.
7. **Discoverability/packaging debt.** The flagship palette is unreachable,
   mobile collapses, and the repo's front door undersells and overclaims at
   the same time.

## Wave 0 — Truth reconciliation (docs say what is true) — IN PROGRESS

- **H0-A** README receipts: fix stale counts (80→278 non-live tests, 190→833
  chat facts, "13→4" example, "latest 41.6"), date-stamp every point-in-time
  number, add `backend/tests/test_readme_receipts.py` so known-rot patterns
  fail CI. *(README.md, new test)*
- **H0-B** README front door: 30-second block + TOC; cut the 21-bullet feature
  wall to ~8, move the rest to `docs/FEATURES.md`; add the omitted flagship
  surfaces (SQL console, Source Ledger, MCP server, gated AI briefing, Signal
  Board, 2019→now history, Trace); fix the "◐ Globe / ▦ Board" description
  (four views); de-duplicate hero.png; add a short "How this was built"
  section that owns the AI-orchestrated process plainly (drop raw agent
  counts); make the "nothing here forecasts" headline the precise claim.
- **H0-C** Move `BEST-IN-CLASS-PLAN.md` + `MONITOR-UX-PLAN.md` from repo root
  into `docs/plans/`, stamp both `✅ EXECUTED` with commits; strip
  career-meta language ("$200K bar", "interview gold") everywhere it appears.
- **H0-D** Stamp FRONTEND-UX-OVERHAUL + PROVENANCE-AND-CONNECTION as executed
  (they shipped within ~24h of being written); add supersession notes where a
  later plan reversed an earlier one (brief default-open vs collapsed).
- **H0-E** Reconcile STANDPOINT-5YEAR ↔ STANDPOINT-VISION: annotate VISION
  P4–P6 with what actually shipped early (reasoner, hyp tier, Nearby, palette,
  ledger, lenses) and what genuinely remains (Action matrix-sharding, P5
  rasters); soften 5YEAR's "P0–P6 genuinely done" and remove the nonexistent
  commit ref; add a one-line precedence note to both (5YEAR governs
  depth/cap strategy; VISION's breadth list is a menu under that cap).
- **H0-F** Regenerate `docs/plans/README.md` (one row per doc, single true
  status, all docs indexed) and rewrite `docs/README.md` (retitle Standpoint,
  correct active-plan pointer, index DATA-ATLAS + writing/).
- **H0-G** ADR housekeeping: dates on all six; re-scope ADR-0002 (DuckDB-SSOT
  applies to the measured spine; the sidecar tier is its own documented
  pattern); ADR-0004 forward-link to the rebuilt news layer; new ADR-0007
  (tier firewall + registry SSOT) and ADR-0008 (dbt as co-equal consumer).
- **H0-H** AI-briefing truth: `reason.py` is deterministic templates — stamp
  `agent_model` honestly, fix the disclaimer and the SourceLedger "derived ·
  AI" badge, align the essay. (Wiring a real model through the existing gate
  stays a possible follow-up; truth ships first.)
- **H0-I** License/tier truth: relabel IMF PCPS series ("© IMF, via FRED, free
  with attribution" — not public domain) in commodities.py, metals.py, and the
  Data Atlas; reclassify the hardcoded `lanes` layer out of SPINE (or stamp an
  honesty_note + schematic intensity labeling).
- **H0-J** Keep ADRs + Data Atlas + one vision doc linked from the README;
  label 5YEAR/AI-NATIVE as satellites in the index rather than front-door
  links.

## Wave 1 — Production correctness — PENDING

- **H1-A** Flag lifecycle: append-only committed ledger
  (`data/state/flags_ledger.jsonl`, keyed by lineage_run_id, force-added in
  refresh.yml like events_state.json); seed `_load_prior_flags` from the
  ledger when `fct_flags` is empty. Receipt: lifecycle continuity test across
  two runs; production flags can be `ongoing`/`resolved` again.
- **H1-B** Cape-reroute exposure: flags carry structured chokepoint refs
  (Suez, Bab el-Mandeb) consumed by `_exposed_lanes`; delay/premium keyed off
  the Cape entry (10d, premium ≠ 0). Receipt: regression test — a Suez-routed
  lane shows exposure when cape_reroute fires.
- **H1-C** Stress index: anchor each chokepoint's "normal" to a long reference
  window (the history.py approach) so sustained collapse keeps driving the
  index; weight by capacity (DWT) share, not vessel count — the docstring
  already claims economic weighting. Disclose the window in the method string.
  Changes published numbers: re-bless golden masters in a dedicated reviewed
  commit; update dbt models/vars + parity + README examples together.
- **H1-D** refresh.yml: own concurrency group (cancel-in-progress: false) so
  deploys can't silently kill the weekly refresh; DERIVED gate block skips the
  layer (demotions.json receipt) instead of aborting the whole refresh; run
  frontend validation BEFORE the data commit; split into two jobs with
  least-privilege permissions (contents:write vs pages/id-token) and
  persist-credentials: false; pin all actions to commit SHAs.
- **H1-E** Freshness honesty: every layer stamps its OWN observation date as
  `as_of` (spine join date moves to `spine_as_of`); contracts gain
  `max_age_days` so a dead feed actually demotes; post-publish assertion that
  snapshot `as_of` advanced; failure notification (issue-on-failure); UI
  stale-data badge past ~10 days.
- **H1-F** Contract coverage: add contracts for `signals_fdr.json` (the file
  actually consumed), stress, timeseries; add them to CORE_STEMS; make the
  contracts CLI list uncontracted sidecars (its docstring already promises
  this).
- **H1-G** ADR-0005 truth in code: extract one shared ordered publish step
  list that BOTH drivers iterate, so Temporal and publish_static cannot
  diverge again.
- **H1-H** timeseries honesty: null for never-observed days (no fabricated
  zeros / forward-fills), per-series `as_of`; drop the bfill in history.py;
  frontend renders gaps as gaps.

## Wave 2 — Detection rigor — PENDING

- **H2-A** Event-replay backtest: run detection week-by-week over the 2019→now
  archive, score against the curated event list (Ever Given, Red Sea,
  Baltimore, Hormuz…) for precision/recall/lead-time; publish the table as a
  doc + CI artifact. The flags ledger (H1-A) feeds a live hit-rate scoreboard.
- **H2-B** FDR calibration: scan-aware p-values (effective-looks correction or
  empirical nulls from block-bootstrapped residuals); count cargo-type tests
  in m; make the white-noise CI predicate exercise the full detect_series
  pipeline.
- **H2-C** CUSUM: implement the documented promote path (CUSUM-confirmed days
  bypass the z pre-filter) or delete it and correct both docstrings.
- **H2-D** Holidays: per-year Lunar New Year dates (static table → 2035);
  scope windows to affected geographies instead of suppressing globally.
- **H2-E** Persistent detection for ports (with its own FDR budget) and a
  persistent cape variant (compare to pre-shift reference; "sustained since
  <date>") so established disruptions stay visible.

## Wave 3 — Frontend & provenance surfaces — PENDING

- **H3-A** Make the flagship navigation visible: ⌘K chip in the topbar
  (dispatching the existing event), a Lenses entry point, search-token hints.
- **H3-B** Mobile: LayerPanel becomes a pill + bottom sheet; stage ≥45vh;
  History reachable on phones; fix the TimeScrubber/LayerPanel occlusion; add
  an overlay-collision regression check (third bug of this class).
- **H3-C** Resilience: ErrorBoundary around every lazy view + chunk-error
  reload prompt; visitor-facing error fallback (retry; DEV-only exporter
  hint); useData fires all fetches concurrently with only snapshot.json
  fatal; validate/clamp deep-link params; keyboard path for Board rows;
  memoize Row + split hover highlight out of buildLayers.
- **H3-D** Provenance completeness: storms/ships dots get ContextTraceCard;
  honesty_note (or kind-default caveat) for quakes/weather/wind/satellite;
  brief cite chips open an inline Trace (computed-by-us before the root
  outlink) with human names; StressDetail renders `<Trace layerId="stress">`;
  HistoryTimeline shows its event citations; ONE canonical disclaimer +
  small badges instead of six near-identical footers; plain-words tier
  lexicon ("measured by us / computed by us / cited as published") fed from
  one place; z/norm/sev tooltips on Board headers.

## Wave 4 — Data layer depth — PENDING

- **H4-A** FRED: official keyed API (Actions secret) with fredgraph fallback;
  drop the UA spoof; collapse the five copy-paste FRED family modules into
  one parametrized spec (golden sidecars prove byte-identity).
- **H4-B** Daily context-only workflow (storms, quakes, tides, marine, space
  weather, GDELT) that skips the PortWatch rebuild; per-layer age badges.
- **H4-C** Ship the two highest-value measured signals already in the catalog:
  USACE LPMS lock delays and a recurring AIS dwell/queue count near top
  ports; stop adding context-ring breadth.
- **H4-D** Signal cleanup: rename per-silo `fdr_significant` →
  `family_fdr_significant` (pooled is authoritative); flip
  `export(write_flags=)` default / delete the legacy preview path; replace
  the 26-adapter zoo in registry/layers.py with one lazy factory.
- **H4-E** Substrate honesty: per-run Parquet partitions keyed by
  knowledge_time (real bitemporality) or soften the docstring; fold
  fct_flags + meta_attribution DDL into storage/schema.sql.

## Wave 5 — Tests, CI, supply chain — PENDING

- **H5-A** Frontend tests: vitest for useMonitorModel/nearby/routing/
  useHistory; wire one Playwright smoke (verify_globe + verify_query against
  vite preview) into ci.yml; add typecheck + lint to the PR-level frontend
  job.
- **H5-B** Un-skip Temporal durability tests in CI (retry probe in its own
  module; e2e against the hermetic fixture DB the dbt job already builds).
- **H5-C** Chat grounding oracle: value-at-path assertions instead of
  substring containment; assert every digit-run in answer text maps to a
  registered fact; refresh.yml runs the data-coupled pytest subset before
  committing.
- **H5-D** Backend ruff + type-check gates (the noqa codes imply a linter
  that isn't there); fix implicit Optionals and the _connections annotation.
- **H5-E** dbt: enforce source freshness in refresh.yml; extend the parity
  gate to all three numeric marts; unit tests proving the guard tests can
  fail (red-case fixtures); exposures for the Globe/snapshot/API; publish
  dbt docs under Pages; `contract: enforced` on marts; label thresholds as
  vars with all-days label parity.
- **H5-F** API/MCP: honor If-None-Match → 304 (with test); AST/import-graph
  proof that MCP handlers only call read-only store functions; consume the
  generated CORE_FILES manifest in useData (or stop emitting it); generate
  TS types from contract shapes for the contracted sidecars.
- **H5-G** Supply chain: SHA-pin all GitHub Actions; self-host the pinned
  duckdb-wasm bundle (lazy chunk, boot budget unaffected); Dockerfiles build
  from lockfiles; pin the Temporal image; bind compose ports to 127.0.0.1.

## Wave 6 — Operability — PENDING

- **H6-A** CONTRIBUTING.md + a short runbook (setup, weekly refresh anatomy,
  failure playbook); seed a CHANGELOG from the shipped waves.
- **H6-B** npm/pip audit steps (advisory) in CI; document the operational
  model honestly in the runbook.

## Verification gates (every wave)

Full backend pytest (non-live) green · dbt build + parity green · frontend
typecheck/lint/build/bundle-budget/grounding green · golden-master re-blesses
are their own reviewed commits · refresh/deploy workflows green on main ·
live site spot-checked after deploy. No wave is "done" undeployed.
