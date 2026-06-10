# Standpoint — the full feature ledger

The [README](../README.md) is the front door; this is the complete inventory, in depth.
Every claim below is the shipped behavior, not a roadmap. Counts and data examples are
point-in-time: unless a bullet carries its own date, they reflect the published store as
of the **2026-06-08 refresh** (data through **2026-05-31**) — the weekly refresh moves them.

---

## The four views

One tier-stamped data store, four ways to read it (`◐ Globe · ▦ Board · ⌗ SQL · § Sources`,
deep-linkable with `#v=globe|board|data|ledger`):

- **◐ Globe** — MapLibre v5 native globe + deck.gl (interleaved) renders 28 chokepoints as
  crisp amber marks and 2,065 ports sized into a hierarchy by real vessel traffic (big ports
  read first), plus sampled live AIS vessels and great-circle lane arcs. A **layer panel**
  groups every overlay into **Freight** (the measured spine — flags / chokepoints / ports /
  vessels / lanes) and **Context** (cited, possibly-related signals — news / storms / wind /
  satellite), each with live counts and fenced by a "possibly-related context, not a stated
  cause" caption + a persistent provenance footer. It answers honestly what the vessels are
  (a point-in-time AIS sample near the chokepoints, not all ships).
- **▦ Board** — a sphere can't be sorted, so a one-click toggle swaps the globe for a dense,
  terminal-style **analytical board** over the *same* data: a sortable table of the 28
  chokepoints + flagged ports (now/day · normal · Δ% · z-score · 120-day trend · cargo mix),
  topped by the stress strip and flanked by a cited **Signals rail**. The table header reads
  "measured · freight spine · computed in Python"; the rail separates a **measured signal**
  (Gatún — numbers *we* compute over the cited ACP record) from **context** (GDELT/USGS/GDACS
  shown as-is, "possibly-related, not a cause"). Pure re-presentation — zero new data or
  compute; click a row, hover to cross-highlight, deep-link with `#v=board`.
- **⌗ SQL** — an in-browser **DuckDB-WASM console** over the exact JSON sidecars the globe
  and the MCP server read. No backend: the store loads into WASM and you (or an agent) write
  real SQL against the tier-stamped catalog — layers by tier, chokepoints under most
  pressure, flags joined to context. It is the visible proof that the store is one clean,
  machine-legible substrate, not a private app format.
- **§ Sources** — the "show your work" page: the registry catalog rendered as a
  human-readable **provenance ledger**. Every layer, its epistemic tier, its cited source +
  license, what it is (the owned metric for measured layers, the honesty note for context
  layers), and how fresh it is. The same catalog an agent reads over MCP, made legible to a
  person.

Plus two overlays that work across views: a **⌘K command palette** (jump to any entity,
layer, or lens) and **History mode** (below).

## The measured freight spine

- **Filterable monitor feed** — every monitored chokepoint + flagged port, filterable to
  **All / Critical / Chokepoints / Ports**, sorted critical-first then by real traffic. Click
  any row → the globe flies to it and a plain-English brief expands with the *real* numbers
  ("Shanghai port calls fell to 18 on 2026-05-25, 79% below its 28-day norm, z = −7.1" — a
  live example from the 2026-06-08 refresh). **Search** by name, country, or status
  (`country:japan`, `is:critical`) lights every match on the globe; hovering a row rings its
  mark.
- **Change-point detection, not threshold alarms** — STL(7, robust) residual → rolling
  z-score **AND** CUSUM **AND** a `ruptures` PELT breakpoint within 7 days, so one-day blips
  are suppressed and only statistically defensible disruptions reach the rail. Detections are
  FDR-controlled (Benjamini–Hochberg across the family of tests), and each flag carries an
  explicit **lifecycle** (`new → ongoing → escalated → resolved`). On the 2026-06-08 refresh
  the rail carries **168 flags** (165 port-level, 3 chokepoint-level) across the ~2,100
  monitored entities.
- **Cargo-aware detection** — beyond the blended counts, the engine reads the per-cargo-type
  flows the warehouse already carries. A port's **dominant cargo stream** is detected on its
  own — so a brief reads *"container calls −38%, tanker +32%"* instead of a muddied total,
  surfacing moves a total-only view erases. Each chokepoint's **average vessel size**
  (transiting tonnage ÷ vessel count) is tracked as an axis **orthogonal to the count**
  (≈ −0.08 correlation), catching fleet-mix shifts the count can't see. Every row shows its
  **vessel mix**; chokepoints add avg vessel size + transiting tonnage.
- **National-dependence weighting** — each port carries its share of its *country's*
  maritime trade (an IMF systemic-importance score). A country's **sole gateway**
  (Mombasa ≈ 99.8% of Kenya's trade) outranks an equally-busy port that is one of many — and
  a flagged systemic port says *"handles ~N% of {country}'s maritime imports"* on its brief,
  with a National-dependence chip in the row.
- **Global Ocean Freight Stress Index (0–100)** — one at-a-glance number in the top bar,
  with a 30-day sparkline and week-over-week momentum. It **blends breadth** (an
  economic-weighted mean of every chokepoint's deviation from its normal throughput) **with
  depth** (the single worst chokepoint), so a concentrated crisis at one strategic strait
  isn't averaged away. Both components are exposed for inspection — and the **StressDetail**
  panel decomposes the number into its per-chokepoint contributors.
- **Cape-reroute detector** — fires only on a real Red-Sea-down / Cape-up divergence; when
  the two routes move in parallel it honestly does not fire, and says so.
- **Time-scrubber** — replay the trailing 120 days; chokepoint glow dims/brightens by each
  day's real count and a flag pulses on the actual date it was detected.
- **History mode (2019 → now)** — the stress index across PortWatch's full record as a
  playable timeline, with the real shocks marked (COVID, Ever Given, the Red Sea crisis…)
  and a persistent "where today sits vs the worst it's been" anchor.
- **World Today ribbon** — a global pulse across the top: ships in transit, port calls, and
  cargo delivered/shipped per day, each with a today-vs-last-week trend + sparkline. Real
  daily sums from the DB.

## Cross-domain measured signals

- **Signal Board** — the non-maritime anomalies the pipeline computes — freight-mode rates
  (truckload / rail / air), inventories-to-sales, commodities, metals, macro, labor — as a
  first-class feed beside the port flags. Each is a z-score **we** compute over a cited
  public index (FRED, IMF PCPS…), FDR-controlled, national + monthly, labelled *association
  only* — so the product reads as multi-domain, not straits-only.
- **Panama Canal leading indicator** — the **ACP**'s own Gatun Lake level + projected
  max-draft CSVs (free, keyless). Lake level drives the transit draft, so a draft cut shows
  up here *weeks before* the PortWatch transit count falls — a signal the count data
  structurally can't provide. (The projected draft is the ACP's own published projection,
  labelled as theirs — Standpoint computes no forecasts.)

## Provenance & agents

- **Trace — the one provenance primitive** — click any datapoint → see its raw input → the
  computation we ran → the published number → the cited source (linked, licensed, dated).
  Rendered identically on flags, the cross-domain signals, unflagged ports/chokepoints, globe
  context dots, and the brief. RAW (cited) and COMPUTED-BY-US are separate steps, never
  collapsed; a `fenced` marker renders the "system context — not this place" band national
  signals require.
- **Ask Standpoint** — a grounded chat that runs **entirely in the browser** over the loaded
  data (no backend, no API key). It answers "what's going on with Hormuz / what's the biggest
  risk / am I exposed / how many ships are out today" — and **only ever states a number it
  can trace to a source file**, enforced by `npm run test:chat`: **833 facts across 39
  questions, 0 ungrounded**, plus a 6-question bait battery that must refuse forecast/causal
  prompts (run 2026-06-09).
- **Knowledge MCP server** — `freight_radar.mcp` exposes the published store to agents over
  the Model Context Protocol: `list_layers` / `get_layer_facts` / `nearby` / `verify`, every
  result facts-with-provenance. There is **no write tool**, and the server refuses to build
  if one appears (`assert_read_only()` at import) — the honesty firewall extended to the
  agent interface.
- **Gated DERIVED briefing** — an offline reasoner reads the published store, selects
  this-week facts, **grounds each through ground-or-abstain** (anything the store can't cite
  is dropped), phrases with fixed templates, and ships only through a **fail-closed gate**:
  every claim must cite a real layer, every number must be entailed verbatim by its cited
  data, zero causal/forecast tokens, and the bait battery must still refuse everything. The
  gate runs before the artifact is written *and* in CI over the committed artifact; the
  module is quarantined so nothing in the fact path can import it.
- **"This week" brief** — a deterministic hero card that assembles 3–6 plain-English,
  fully-cited bullets from the sidecars at publish time. The figures are string-substituted
  from real computations; the prose is a template, so no statistic can be hallucinated.

## Context layers (cited, possibly-related — structurally unable to touch the facts)

Context layers ride the sidecar registry: they carry no computed metric and *can't* write to
the fact tables. Adding one is one Python module + a registry tuple + one render.

- **Geo-tagged world news** — one dot per real, geo-located article from a recent **GDELT
  2.0 GKG** window, coloured by topic (economy · trade & logistics · energy · conflict ·
  disaster); click a dot to open the source article. Pulled from GDELT's keyless raw 15-min
  export in the weekly job, filtered Python-side to business/disruption themes, de-duped and
  capped. (A first cut on GDELT's DOC 2.0 query API was **cut** rather than shipped, because
  that endpoint rate-limits shared IPs so hard the weekly CI would publish an empty layer —
  see [ADR-0004](adr/0004-cutting-the-gdelt-attention-feed.md). This rebuild uses the static
  export that never throttles. Same bar both times: an empty, pipeline-polluting feed fails
  it; a robust, cited one clears it.)
- **Live storm layer** — *active* tropical cyclones from **NHC** `CurrentStorms` (Atlantic +
  E/Central Pacific, the official US cone) **and GDACS** (every other basin — the W-Pacific /
  Indian-Ocean systems near Malacca / Hormuz / Taiwan / Luzon that NHC never issues), deduped
  (NHC stays authoritative), attached to any flag within 500 km as a *possibly related*
  physical driver — **never** a stated cause. Each active system is plotted on the globe with
  an active-cyclone count in the header that lists them and flies you to each. Fetched
  server-side (the NHC feed sends no CORS header) and silent off-season.
- **Natural hazards / official events** — IMF PortWatch (**GDACS**) cyclone/flood/earthquake
  alerts that hit monitored ports, matched by exact port ID, with flag corroboration only
  when genuinely contemporaneous (±30 days) and the GDACS magnitude shown.
- **Earthquakes** — one terracotta dot per **USGS** M4.0+ event in the past 7 days, sized by
  magnitude; click for the USGS event page. Public-domain, keyless, **observed** (never a
  model output).
- **Ambient wind layer** — an animated global **wind field** (thousands of GPU particles),
  so weather is visible *everywhere*, not just at storms. Real **NOAA GFS** 10 m wind, baked
  into small u/v PNGs at publish time and rendered with `weatherlayers-gl`; a **forecast
  scrubber** sweeps the field now → +4 days (GFS f000–f096 — GFS's own model output,
  labelled as theirs, "updated weekly").
- **Real satellite imagery** — a toggleable **NASA GIBS** VIIRS true-color basemap drapes
  actual cloud systems over the globe; dated and cited, off by default.
- **Live vessel positions** — **real AIS** positions near the 28 chokepoints (free
  **aisstream.io** key → a ~70 s snapshot at publish), plotted as teal dots with name/heading
  tooltips. A point-in-time *sample* near the chokepoints — honestly not "all ships".

## Business exposure

- Point a trade CSV at it (LOCODEs or port names, region column optional) and each
  disruption maps to *your* lanes with a banded **Cost-of-Disruption stack** (carrying cost +
  reroute premium), coverage reporting ("X of N lanes modeled"), and a "show your work"
  method panel. Working capital is held separate (locked ≠ lost), and the stack's total is
  exactly carrying + reroute premium — no fabricated lines.

## Pipeline & operations

- **Write-Audit-Publish ETL** — each fresh pull lands in **staging** tables; an enumerable
  data-quality suite audits it; only on a clean verdict are the rows **atomically swapped**
  into the live `fct_*` tables inside one DuckDB transaction, with a deterministic
  `lineage_run_id` recorded. A renamed upstream column, a dropped pagination page, or a
  decayed `portid`→geometry join **raises** and leaves the prod fact table unchanged — the
  pipeline refuses to publish bad data rather than briefly serving a half-empty map.
- **Self-refreshing in production** — a scheduled GitHub Action (`refresh.yml`, weekly +
  on-demand) rebuilds the DuckDB from PortWatch, re-runs detection + every enricher, and
  commits the changed sidecars; that push auto-deploys. The live site stays current without
  anyone running anything by hand.
- **Durable loop (verified in a test harness)** — the same fetch → detect → attribute →
  enrich → publish steps are wrapped in a **Temporal** workflow + Schedule, with durability
  proven end-to-end on Temporal's time-skipping test server (kill the worker mid-run, it
  re-drives from the last completed activity). The scheduled Action above is the always-on
  production driver of those identical `publish_static` steps.

## dbt analytics layer (`dbt/`)

DuckDB is a **substrate**, not a single app's private store — the globe is one view of it; a
second, co-equal consumer is a **dbt project** (`dbt-duckdb`) pointed at the same
`data/freight_radar.duckdb`. dbt doesn't re-fetch anything: it declares the pipeline's landed
tables as **sources** and re-expresses the transforms as a `raw → staging → marts` lineage,
with the **fail-loud ETL guards re-expressed as dbt tests**.

```
sources (main.*)            staging (views, main_staging)        marts (tables, main_marts)
  dim_chokepoint  ─┐          stg_chokepoints / stg_ports          mart_chokepoint_pressure   ← export_snapshot._chokepoints
  dim_port         ├──────▶   stg_chokepoint_daily / _port_daily ▶ mart_port_activity         ← export_snapshot._ports
  fct_chokepoint_daily        stg_flags                            int_chokepoint_stress ─▶ mart_freight_stress_index  ← narrative/stress.py
  fct_port_daily  ─┘                                               mart_active_flags          ← detection serving
  fct_flags
```

- **Re-expression, not new analysis.** The marts reproduce the existing numbers — the 28-day
  rolling baseline (`pct_change`/`z-score`), the per-port latest snapshot, and the stress
  index (80th-pctile normal → deviation squash → causal 3-day smoothing →
  `100·(0.6·breadth + 0.4·depth)`). The pipeline's named constants are dbt `vars`, and
  DuckDB's `round_even` matches Python's banker's rounding so the figures are identical, not
  merely close.
- **The ETL guards become dbt tests.** Generic schema tests plus **singular tests** for the
  heavier invariants: the D1 join-coverage gate (`portid`→geometry ≥ 0.95), the cargo-mix
  reconciliation (leaf vessel types sum to the headline totals), and a stress-index range
  check. `dbt build` materializes 10 models (4 tables + 6 views) and runs **82 data tests** —
  green or the build fails.
- **Reconciled to the Python pipeline, exactly.** Every materialized figure was diffed
  against the functions it re-expresses: on the 2026-06-08 refresh the stress index matches
  on **all 120 daily points** (max |Δ| = 0; latest = 41.6 / "high", data through 2026-05-31),
  chokepoint pressure on all 28×5 computed fields, port activity on portcalls/vessels +
  full-precision shares — **0 mismatches**.
- **Isolation.** dbt writes to `main_staging` / `main_marts`; the app + API still read `main`
  only, so the analytics layer never collides with the pipeline's own tables and the
  production refresh job never imports dbt.
- **CI is hermetic.** The prod warehouse is gitignored, so CI rebuilds a tiny fixture DB from
  committed CSVs (`dbt/ci/`) using the **exact prod DDL** and runs `dbt build` against it —
  the dbt layer is enforced on every push, not decorative.
- **Warehouse-portable.** Models are plain SQL on the standard `source()`/`ref()` lineage;
  `profiles.yml` carries a commented **BigQuery** target showing the same models run on a
  cloud warehouse by swapping the adapter. DuckDB is the live, tested target.

```bash
cd backend && uv sync --extra dbt                                   # dbt-core + dbt-duckdb
uv run dbt deps  --project-dir ../dbt --profiles-dir ../dbt         # vendor dbt_utils
uv run dbt build --project-dir ../dbt --profiles-dir ../dbt         # models + tests (dev target)
uv run dbt docs generate --project-dir ../dbt --profiles-dir ../dbt # lineage + data dictionary
```

## Build-time verification receipts

Receipts recorded when each capability landed (each tied to its build moment — the current
CI-enforced receipts live in the [README](../README.md#receipts)):

- **Data plumbing** — the initial 180-day backfill landed 4,984 chokepoint + 363,440 port
  daily rows; `portid`→geometry join 1.00; live contract test green; idempotent re-pull adds
  0 rows, 0 PK duplicates.
- **Detection** — flag numbers spot-checked against the raw DuckDB at build; detector tests
  include *fires on a real collapse, not on weekly seasonality*, *PELT gate suppresses
  spurious spikes*, *Cape fires on divergence / quiet when parallel*, *holiday suppresses a
  benign dip*.
- **Cargo-aware detection** — tests prove the dominant-cargo detector fires on a
  container-only drop while the blended total is flat **and** stays additive (an
  evenly-spread drop yields the blended flag only, never a duplicate); the avg-vessel-size
  detector fires on a size shift with a flat count. The per-entity cargo mix is asserted to
  sum exactly to the headline total (PortWatch's leaf-type invariant).
- **National-dependence weighting** — a sole gateway outranks an equally-busy peer at
  identical vessel count; weights stay in the 0.6–1.0 band; the dependence brief line fires
  for a systemic port and is silent for a minor one.
- **Live storm layer** — fixture tests prove NHC/GDACS normalization, the NOAA-duplicate
  dedup, and radius + lifecycle matching; verified against the live feeds with the honest
  dormant state when no storm is within 500 km of a flag.
- **ETL guards** — unit-pinned and **prod-verified by dispatching the weekly Action**: a full
  backfill ran the silent-column-drop guard, the fetch-completeness `verify_count`, and the
  non-retryable join-coverage gate with zero false-raises.
- **Durable loop** — the workflow runs end-to-end on Temporal's in-process time-skipping test
  server; a 2nd identical run makes **zero** attribution calls (dedup ledger); RetryPolicy
  re-drives a transient failure.
- **Narrative layer** — the stress index reads `calm` on an all-normal system and `high` when
  a single strategic strait collapses; a sustained level-shift still scores stressed at the
  latest day; the event ledger diffs appeared/escalated/resolved across runs; and the brief
  is verified to **never state a number the stress index contradicts**.
- **Frontend** — headless-Chrome screenshots confirm the globe renders (WebGL2 + interleaved
  deck.gl), the stress gauge + brief render, the chat answers with citations, flags are
  clickable (fly-to + real brief), and the scrubber replays real history — **0 console
  errors**.
- **Business depth** — a real-world CSV (LOCODEs, alternate spellings, no region column)
  resolves instead of silently zeroing; coverage is reported; the cost stack's total is
  exactly carrying + reroute premium.
- **Hazard corroboration** — synthetic GDACS events prove the matcher: exact port-ID matches
  + chokepoint proximity, old/non-infra events dropped, and a flag is corroborated **only**
  by a contemporaneous (±30d) hazard — never a stale one.
