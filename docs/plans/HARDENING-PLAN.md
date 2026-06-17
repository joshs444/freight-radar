# Hardening plan — fix everything the adversarial review found, at the root

**Status: IN PROGRESS — Wave 0 ✅ 2026-06-09; foundation track folded in (council-validated); Wave 1a ✅ 2026-06-16 (F1 ledger + lifecycle, H1-A/B/D/G); Wave 1b in progress — H1-C ✅ + F3 slice 1 ✅ 2026-06-17, F2 slice 1 next.**
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

## The foundation track (council-validated 2026-06-09)

Root causes 2–4 are not fixed by patches — they're fixed by three small
foundations. Each was pressure-tested against the real code by an independent
architecture council (verdicts: build-modified — right move, smaller than the
sketch). Wave items the foundations absorb are marked below; the rest of the
waves stay as listed.

- **F1 — the system remembers itself** (+ **F4 — the adjudication engine**).
  Three thin, force-added JSONL ledgers under `data/state/` (the proven
  `events_state.json` pattern — NOT per-run Parquet partitions, rejected on
  `.git`-growth math; bulk history stays derivable from git + PortWatch):
  `flags_ledger.jsonl` (one slim line per flag per run, ~41KB/wk),
  `run_ledger.jsonl` (one line per run: spine `as_of`, stress, per-layer
  freshness, ~2KB/wk), `claims.jsonl` + `adjudications.jsonl` (F4). New
  `ledger.py` (append/read, CLI step in refresh.yml after the parity gate;
  appends never inside `publish_static`, keeping the golden harness
  deterministic). The ledger becomes the ONLY prior-flags source for
  lifecycle (drops the `fct_flags` read — CI and local behave identically).
  F4: every new flag registers a claim with resolution criteria
  (`evaluate_after = as_of + 21d`, confirm = z still clears the bar on the
  revised series truncated at `as_of`); the adjudicator's core
  `evaluate_at(series, as_of, cfg)` is the same primitive H2-A's backtest
  replays. Outcomes publish as a contracted `adjudications.json` — a public,
  falsifiable hit-rate record (claims about the measured present adjudicated
  against revised data; never a forecast). ADR-0009 records the design + the
  hard rule: bulk per-run artifacts only ever via GitHub Releases, never git.
  *Absorbs H1-A, half of H2-A, H4-E (option A), the run-ledger half of H1-E.*
- **F2 — claim-first prose.** `derived/contract.py`'s `Claim` already exists;
  the real gap is cites that resolve to layers, not VALUES. Add
  `Cite{layer, query, value, fmt}` (JSON-pointer or a registered selector in
  `honesty/selectors.py`), `slots` on `Claim`, and `CitedNarrative` (typed,
  source-mandatory exemption for curated history blurbs/news titles). New
  `honesty/render_check.py`: per-cite value equality against the published
  sidecar + digit-run coverage (every number in rendered text is a template
  literal or `fmt(cite.value)`). Migrate `narrative/brief.py` claim-first
  with BYTE-IDENTICAL rendered text (golden test — voice must not regress);
  `brief.json` only gains an additive `slots` field, frontend untouched.
  Then the chat: `Fact` gains `path`/`fmt`, `check_chat.mjs` becomes
  value-at-path (kills the substring oracle), and ask.ts's one client-side
  derived number (the Gatún draft cut) moves into `gatun.py`'s published
  payload. *Absorbs H5-C, the bag-of-numbers entailment + boilerplate-key
  holes, and the firewall-skips-brief/captions/chat finding.*
- **F3 — one shape registry generates the contracts.** *(slice 1 ✅ 2026-06-17;
  catalog JSON-Schema/hash = slice 2, pending.)* New
  `registry/shapes.py`: a deliberately tiny field-spec grammar (8 type
  constructors, capped) keyed by output stem. Three renderers, one source:
  `contracts.py` SIDECAR_CONTRACTS derived from Shapes (equality-tested
  against today's literals in the migration commit, then literals deleted);
  `types.gen.ts` for ~14 stems / ~35 interfaces (types.ts re-exports;
  byte-identity gate extends `test_registry_codegen.py`); JSON Schema +
  per-shape hash embedded in `catalog.json` (slice 2) so MCP/AI consumers
  get a versioned contract through the existing `list_layers`. `useData.ts`
  imports the generated CORE/OPTIONAL manifest (kills the dead-codegen
  finding). Explicitly NOT built: dbt YAML generation (tables ≠ sidecars;
  hand judgment in severity/descriptions stays) — the one real duplication
  (flag `kind` values) gets a parity test. Typed validation is CI-only for
  two weekly cycles before it may gate the production demote path. Derived
  frontend-only UI shapes stay hand-written. *Absorbs H1-F, most of H5-F,
  the schema_version gap; `max_age_days` (H1-E) gets its one home here.*
  **Slice 1 shipped:** `registry/shapes.py` (8 capped constructors + a `RAW`
  escape hatch); `SIDECAR_CONTRACTS` derived from it (migration test pins the
  derived dict to the old literals; literals deleted); **H1-F closed** —
  contracts added for `signals_fdr`/`timeseries`/`stress` and the latter two
  added to `CORE_STEMS` (contracts CLI now 20/20 on live data); `useData.ts`
  drives off the generated `CORE_FILES`/`OPTIONAL_SIDECAR_FILES`/`APPDATA_KEY_MAP`
  manifest (dead-codegen finding closed); `types.gen.ts` generates the
  context-ring interfaces (spine/signals/UI stay hand-written) with a
  byte-identity gate; flag-`kind` parity test added. Receipts: backend non-live
  312 passed · tsc/lint/parity(208)/chat/build/bundle green · codegen leaves no
  diff. Built by a worktree agent, gate-verified + adversarially reviewed by the
  orchestrator before merge.

## Wave 0 — Truth reconciliation (docs say what is true) — ✅ EXECUTED 2026-06-09

All ten items landed in one wave (3 agents, disjoint file ownership; receipts
re-verified by the orchestrator: 285-test non-live suite green, frontend
typecheck/lint/grounding (833 facts)/exposure-parity (168 flags)/build/budget
green, codegen byte-stable, zero stale statuses or career-meta language left).
Note: ADR-0008 shipped as "the sidecar store: publish-time fetch gated by
contracts" (what ADR-0002's amendment needed) rather than the dbt note
originally sketched below — dbt-as-co-equal-consumer is covered in
README/FEATURES instead.

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
  career-meta language everywhere it appears — docs stay product-voiced.
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

## Wave 1 — Production correctness — IN PROGRESS (1a ✅ executed 2026-06-16; 1b/1c pending)

Runs as sub-waves of ≤3 parallel agents with disjoint file ownership.
**1a:** F1 slices 1–2 (ledger + lifecycle + run ledger + ADR-0009) ·
H1-B + H1-G · H1-D (all workflow edits, including the F1 refresh steps).
**1b:** H1-C (golden re-bless) · F3 slice 1 (absorbs H1-F) · F2 slice 1.
**1c:** H1-E remainder · H1-H · F4 slice (claims + adjudications) ·
F2 slice 2 (chat oracle, absorbs H5-C).

**1a EXECUTED 2026-06-16.** Built by 3 disjoint agents, then put through a
5-dimension adversarial review (find → independently verify each finding); 9
confirmed issues were root-caused and fixed before landing — chiefly: the ledger
keyed runs on the spine `as_of` alone (which repeats weekly), so a same-date
re-detection silently froze flag state → now keyed on `(run_key, generated_at)`
with "latest" by recording order; a gate-trip that demoted `ai_briefing` deleted
the committed file and would have crashed CI on every later push → the gate test
tolerates a receipted demotion; and `contracts --demote` blind-overwrote the
reasoner's demotion receipt → both writers now merge the shared `demotions.json`.
Receipts: backend non-live 305 passed · dbt build 92 + Python↔dbt parity ·
frontend typecheck/lint/parity(186)/chat(909)/bundle · actionlint(×3) · all 8
action SHA-pins resolved · ledger CLI runtime-verified.

- **H1-A** ✅ Flag lifecycle — **absorbed by F1 slice 1** (see the foundation
  track): committed `flags_ledger.jsonl` as the ONLY prior-flags source.
  Receipt: `test_lifecycle_survives_a_fresh_db_rebuild` (continuity across two
  fresh-DB runs) + `test_same_spine_rerun_records_revised_flag_state`;
  production flags can be `ongoing`/`resolved` again.
- **H1-B** ✅ Cape-reroute exposure: flags carry structured chokepoint refs
  (Suez, Bab el-Mandeb) consumed by `_exposed_lanes`; delay/premium keyed off
  the Cape entry (10d, premium ≠ 0); Python/JS parity. Receipt: regression test
  — a Suez-routed lane shows exposure when cape_reroute fires.
- **H1-C** ✅ (2026-06-16) Stress index: each chokepoint's "normal" is now the
  80th-pct of its FULL PortWatch record (the history.py approach), computed by the
  exporter via `quantile_cont` so a sustained collapse keeps driving the index
  instead of fading once it fills the trailing window; weighted by capacity (DWT)
  share, not vessel count. The dbt mirror (`int_chokepoint_stress`) computes the
  same over full history; window disclosed in the method string. Receipts:
  Python↔dbt parity green (fixture 42.0), dbt build 92, golden re-blessed
  (stress/timeseries/brief/world), full non-live suite green; README/FEATURES
  example numbers re-dated to the post-refresh live value on deploy.
- **H1-D** ✅ refresh.yml: own concurrency group (cancel-in-progress: false) so
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
- **H1-F** ✅ Contract coverage — **done via F3 slice 1**: signals_fdr/
  stress/timeseries now have Shapes (contracts derive from them); stress +
  timeseries added to CORE_STEMS; contracts CLI now covers 20/20 sidecars and
  validates the live data clean.
- **H1-G** ✅ ADR-0005 truth in code: extract one shared ordered publish step
  list that BOTH drivers iterate, so Temporal and publish_static cannot
  diverge again.
- **H1-H** timeseries honesty: null for never-observed days (no fabricated
  zeros / forward-fills), per-series `as_of`; drop the bfill in history.py;
  frontend renders gaps as gaps.

## Wave 2 — Detection rigor — PENDING

- **H2-A** Event-replay backtest: run detection week-by-week over the 2019→now
  archive, score against the curated event list (Ever Given, Red Sea,
  Baltimore, Hormuz…) for precision/recall/lead-time; publish the table as a
  doc + CI artifact. **Half-absorbed by F1/F4**: `evaluate_at()` is the shared
  replay primitive, and the live hit-rate scoreboard is a read of
  flags_ledger + adjudications; the 2019→now archive sweep remains this item.
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
- **H4-E** Substrate honesty — **option A chosen via F1**: the run ledger is
  the knowledge-time record; soften the substrate docstring to point at it
  (committed Parquet partitions rejected on growth math; bulk artifacts only
  ever via GitHub Releases per ADR-0009). Remnant kept here: fold
  fct_flags + meta_attribution DDL into storage/schema.sql.

## Wave 5 — Tests, CI, supply chain — PENDING

- **H5-A** Frontend tests: vitest for useMonitorModel/nearby/routing/
  useHistory; wire one Playwright smoke (verify_globe + verify_query against
  vite preview) into ci.yml; add typecheck + lint to the PR-level frontend
  job.
- **H5-B** Un-skip Temporal durability tests in CI (retry probe in its own
  module; e2e against the hermetic fixture DB the dbt job already builds).
- **H5-C** Chat grounding oracle — **absorbed by F2 slice 2** (value-at-path
  Facts + digit-run coverage). Remnant kept here: refresh.yml runs the
  data-coupled pytest subset before committing.
- **H5-D** Backend ruff + type-check gates (the noqa codes imply a linter
  that isn't there); fix implicit Optionals and the _connections annotation.
- **H5-E** dbt: enforce source freshness in refresh.yml; extend the parity
  gate to all three numeric marts; unit tests proving the guard tests can
  fail (red-case fixtures); exposures for the Globe/snapshot/API; publish
  dbt docs under Pages; `contract: enforced` on marts; label thresholds as
  vars with all-days label parity.
- **H5-F** API/MCP: honor If-None-Match → 304 (with test); AST/import-graph
  proof that MCP handlers only call read-only store functions. The manifest
  consumption + TS type generation halves are **absorbed by F3**.
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
