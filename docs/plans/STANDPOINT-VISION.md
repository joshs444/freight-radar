# Standpoint — The Year Vision

_A dependency-ordered, year-horizon plan to evolve Standpoint (the repo still slugged
`freight-radar`) from a ~10-layer ocean-freight globe into an **honest, unified,
lineage-complete model of world state** — every relevant **free** dataset normalized into one
tier-stamped, **agent-legible** store, with the globe + board + chat + AI agents as its lenses.
The globe is the flagship view; **the store is the product** ([§1](#1-north-star),
[§10](#10-the-substrate-reframe-north-star-correction--and-its-critic))._

Produced by multi-agent research passes (data scouts → architecture / UI / governance → roadmap
→ an **adversarial critic**), then a second pass that reframed it around the data substrate. The
critics' corrections are folded in below and recorded in [§9](#9-what-the-adversarial-review-changed)
and [§10](#10-the-substrate-reframe-north-star-correction--and-its-critic). The full source
catalog is [DATA-SOURCES.md](DATA-SOURCES.md) (93 sources). **This is a map, not a sprint** — we
execute one shippable phase at a time, however long it takes.

---

## 1. North star

**The product is not the globe — it's the substrate beneath it.** One queryable, tier-stamped,
**lineage-complete model of world state**: every relevant *free* dataset ingested, connected,
and normalized into one store where **any number traces back to the exact observation and
method that produced it.** The globe, the board, the chat, and **AI agents** are all *lenses*
that read **from** the store — none owns data, none can write a fact the store didn't compute.

Why this is the real north star, not the map: a human can hold maybe 3–5 of ~93 connected
series in working memory; an **agent** querying a clean, uniformly-keyed, provenance-stamped
store can reason across **all** of them at once — *breadth of simultaneous grounding* no human
eye reaches. So the substrate must be **agent-legible** (uniform grain, keys, tier, lineage),
not merely human-visual. And the honesty brand is exactly what makes the store worth more to an
agent than a pile of CSVs: clean epistemic tiers, no cross-layer causation or forecast baked in
**as fact**, complete lineage → **trustworthy ground truth for humans and machines alike.**

**The globe stays the flagship** — visual, impressive, relevant, and trusted *because
everything on it derives from that substrate.* It is the most legible proof the store is
correct. But the store is what ships. The honesty model stays the spine of it all: one measured
freight **SPINE**, N self-owned measured **SIGNALS**, a ring of cited **CONTEXT** — and a
fourth, strictly-downstream **DERIVED** tier for agent commentary ([§2](#2-the-honesty-model-made-structural)) —
all **enforced by construction, not by prose**: a layer (or an agent) that tries to bridge into
the freight detector **literally cannot merge**.

> **Build-order discipline (the critic's load-bearing warning).** The substrate's value lives
> in the *boring 80%* — the typed registry (which **does not exist yet**), the **structural**
> firewall (still a comment, not a test), crosswalk correctness, and freshness enforced as a
> hard gate across ~93 scrapers. **Not** the exciting 20% — a grand unified schema, a reasoning
> agent. Those are *earned*, built downstream and **last**. A maintainer who starts at the
> cathedral ends with a beautiful empty store and a globe that stopped getting layers. We earn
> the substrate through **P0–P1**; the reasoning agent is the **capstone**. Separate
> *substrate-for-agents* (a correct, tier-stamped, lineage-complete **read** store — earn it
> now) from *the agent that reasons* (build dead last, hardened like nothing else), and never
> let the second masquerade as the first.

## 2. The honesty model, made structural

`measured` vs `context` is **epistemic — who computed the number** — not a ranking.

| Tier | Definition | Today |
|---|---|---|
| **SPINE** (exactly 1) | We own the *full chain*: ingest → fact tables → change-point detection → gated flags → the 0–100 stress index. Carries the product thesis ("disruption shows up in throughput weeks before the press"). | Ocean-freight throughput (28 chokepoints) |
| **SIGNAL** (small, vetted N) | We compute a defensible Python scalar over **raw observed** inputs and own the method. Stands alone; **never** wired into the spine or a forecast. | Gatún draft, business exposure/cost |
| **CONTEXT** (the broad ring) | Someone else's cited raw value shown as-is — fetched, filtered, geo-placed, labelled by us, but **not** transformed into a number we claim. "Possibly-related, not a stated cause." | GDELT news, USGS quakes, GDACS, storms, GFS wind, GIBS |
| **DERIVED** (agent · downstream · the capstone) | What a non-deterministic reasoner *said about* the facts — **commentary the store quotes, never a number it owns** (`metric = null`, always; if it could own a number it would have to walk the SIGNAL gates instead). Read-only; every claim **cited** to the facts it used; association-grammar only; born in a quarantined namespace. Can never mutate the store or feed the detector. | (built last, P6) |

**Every record carries its tier + four timestamps + a `lineage_run_id`** — so
SPINE-vs-SIGNAL-vs-CONTEXT-vs-DERIVED is a **per-row** epistemic fact, not a per-file
convention. **The store never carries a cross-layer coefficient, correlation, lag, or forecast
as a fact** — those are forbidden by construction. That per-row discipline is exactly what lets
an agent reason over the *whole* store without ever being handed an un-tiered or untraceable
number.

The world is connected — which is **exactly why we never assert the connection in the
numbers.** Connectedness asserted = fabricated causation = the centrum failure mode. The only
honest way to add a measured signal is the gated **CONTEXT → SIGNAL promotion pipeline**
([§7](#7-honesty-at-scale-governance)).

## 3. Where we are today (the baseline this plan builds on)

Shipped + live on `joshs444.github.io/freight-radar`: the freight SPINE (STL + z-score + PELT
change-points, gated flags, stress index); measured SIGNALS (Gatún, exposure); CONTEXT layers
(GDELT geo-news, USGS quakes, GDACS hazards, NHC/GDACS storms, GFS wind + forecast scrubber,
NASA GIBS satellite); the **globe** *and* the sortable **board**; a client-side grounded chat;
Write-Audit-Publish ingest; a weekly self-refresh GitHub Action; machine-enforced honesty
tests (causal-verb ban, sidecar-firewall).

**Honest debts this plan pays down:** honesty currently lives in *prose* (hand-written
sections, repeated `SOURCE/DISCLAIMER` trios); three lists drift by hand (`ENRICHERS`,
`_SIDECARS`, the `LayerId` union); the firewall is a string-grep, not structural; there is no
multiplicity discipline (fine at 1 spine, dangerous at 50 detectors). P0–P1 fix all of this.

## 4. Architecture — the typed descriptor (the unlock)

One shape every layer instantiates; the honesty taxonomy becomes *structural*:

```
LayerDescriptor {
  id            // stable slug == sidecar name == LayerId (e.g. "quakes")
  kind          // 'SPINE' | 'SIGNAL' | 'CONTEXT'  ← drives EVERYTHING below
  compute       // 'python-scalar' (SPINE/SIGNAL) | 'passthrough' (CONTEXT)
  raw_inputs[]  // the cited observed inputs (must NOT be another party's forecast/score)
  writes_flags  // must be false unless kind==SPINE  (firewall)
  reads_detector// must be false unless kind==SPINE  (firewall)
  metric|null   // the owned statistic + method string (null for CONTEXT)
  source{ name,url,license,auth_model,cost_class,attribution }
  refresh       // 'weekly' | 'daily' | 'on-demand'  ← matrix shard
  render        // point|raster|flow|region|series|tile + legend + honestyNote
  default_on    // first-paint budget gate
}
```

- **Mirrored registry** — `backend/freight_radar/registry/layers.py` is authoritative; TS
  (`LayerId`, `LayerVisibility`, the panel sections, the `useData` fetch manifest) is
  **generated** from `registry.json`. Adding layer #51 is **one append**, not a 7-file
  two-language hand-edit. A CI test asserts the Python and TS id-sets are identical.
- **Two-lane pipeline** — `kind` selects the lane: SPINE/SIGNAL numbers go through
  generalized **Write-Audit-Publish** (staging → audited `CHECKS` → atomic swap → deterministic
  `lineage_run_id`); CONTEXT rides **sidecar-only `enrich`** (writes its own JSON, swallows
  failure, degrade-to-absent). **A CONTEXT layer is given a read-only capability object** and
  the import-graph test proves it cannot import the flags/fact-table writers — the firewall is a
  **compile/CI fact, not a grep.**
- **Honest cross-layer surface** ([§6](#6-ui-evolution), built *last*): co-location / co-timing
  shown; correlation, lag, "drives", and any coefficient **never** computed.

### The right model — five canonical axes, **time first** (the keystone)

Getting the *data model* right is the foundation; every surface is just a lens on it. The store
rests on five canonical axes, and **time is the keystone** — the one axis *every* source shares
(not all have a clean entity or geometry), co-occurrence is fundamentally a *temporal*
intersection, and **every honesty rule the brand makes is a temporal rule.**

1. **Time — bitemporal + grained.** Two clocks on every fact: **valid-time** (when it happened /
   was measured in the world — `source_observed_at`) and **knowledge-time** (when *we* learned it
   — `fetched_at`/`generated_at`). Plus **grain** (`day|week|month|quarter|year|instant|window`)
   and shape (**instant** quake vs **interval** daily value vs **window** GDELT slice). Stored
   canonical UTC ISO-8601; time zones live only at the render edge.
2. **Entity** — what a number is *about* (the crosswalk; the second-most-dangerous axis — a
   silent mis-join mis-attributes a number).
3. **Metric** — what is measured (unit, direction, **tier-by-construction**).
4. **Provenance / tier** — *who* computed it, over what, with the full lineage chain.
5. **Geometry** — *where* (point/line/polygon/footprint), downstream of entity.

**The core primitive is the bitemporal as-of query:** _"the value for (entity, metric) at
**valid-time T**, as **known at knowledge-time K**."_ Globe-now, the board, the time-scrubber,
the 2019→now replay, and an agent's *"what did we know about Hormuz on 2026-05-25"* are all **one
query shape** — get the temporal model right and every surface falls out of it.

**This is where honesty lives or dies:**
- **No fake-live** = freshness is `now − valid_time` ("N days old"), never `now − fetched_at`
  dressed up as "now."
- **No-hindsight history** = the replay must filter to `knowledge_time ≤ scrub_date` and show the
  value **as it was known then** — sources *revise* the past (World Bank, OECD, even PortWatch),
  so a naive replay paints today's hindsight onto 2020 and lies. Bitemporality keeps
  *as-reported-then* and *as-known-now* both, each lineage-stamped.
- **Grain discipline** = a daily number and a monthly number are never compared as same-day; a
  join across grains without explicit resampling is a **typed/CI error, not a silent one.**
- **Forecast** = the *only* rows with a **future valid-time** are a model layer's own output (GFS
  `f024` = a value *for* +24h, generated now) — clearly tiered, never a freight forecast; an agent
  may never emit a future-valid-time fact at all.

### The substrate — one *thin fact index*, not one giant schema

The store generalizes today's `dim_*`/`fct_*`/`meta_*` (real on disk) into a star around four
canonical dimensions + **one long, tier-stamped fact**. Crucially, `fct_observation` is a **thin
unifying index**, *not* the place all data lives — per-layer sidecars stay the payload; the
index is what makes the whole thing joinable and agent-queryable.

- **`dim_entity`** — the join glue: a stable `entity_key` for any *thing a number can be about*
  (chokepoint, port, country, gauge, lake, grid-cell, lane, basin), with crosswalk columns
  (LOCODE, FIPS, H3, `source_native_id`) so a US-Census port-id, a PortWatch portid, and a
  UN/LOCODE resolve to **one** entity. **This crosswalk is where the honesty brand quietly dies
  if it's wrong** — a bad join silently mis-attributes a number — so it ships behind a
  **correctness gate, not just a coverage gate.**
- **`dim_geo` / `dim_metric` / `dim_layer`** — geometry side-table (point/line/polygon/raster
  footprint); the measure dictionary (name, unit, direction, **tier-by-construction**); and the
  materialized `LayerDescriptor` (the single registry Python + TS generate from).
- **`fct_observation`** — `(entity_key, date_key, grain, metric_key, layer_key, value, tier,
  method, source_observed_at, fetched_at, transformed_at, lineage_run_id)`. Today's
  `fct_chokepoint_daily`/`fct_port_daily` become rows here; the five data shapes
  (point/series/flow/region/raster) all collapse onto it — and **rasters never enter DuckDB**:
  only the offline-precomputed *zonal scalar* lands as a row, the tile PNG ships as a sidecar.
- **`agent_inference`** — **separate, append-only, never joined in as fact.** Agent claims live
  here (`tier='DERIVED'`, `cites[]` of `lineage_run_id`s, `agent_model`, `prompt_hash`). This is
  the structural firewall for AI: the same boundary that keeps a CONTEXT sidecar from writing
  `flags.json`, extended to the reasoner.

**Every surface is a pure read** of this store; none can write a fact. `snapshot.json` /
`flags.json` / `lanes.json` become **materialized views** over `fct_observation`; the board's
measured/context split is a `GROUP BY tier`; the chat grounds by `SELECT`-ing rows and quoting
their `method` + `source` + timestamps.

**Storage reality (zero-cost, single-maintainer, static).** The DuckDB file *is* the substrate,
built **server-side in the weekly Action** (never shipped whole, never on the page-load path).
The client still gets the **same per-layer sidecar JSON** it does today — now regenerated as
deterministic `SELECT … WHERE layer_key=?` exports of the store. And the agent lens needs **no
backend**: ship a compact **read-only Parquet/DuckDB export to Pages**, queryable in-browser via
**DuckDB-WASM** at zero marginal cost — so an agent gets the *whole uniform store* client-side,
and the heavy build stays in the weekly Action.

## 5. The roadmap (P0 → P6, ~12 months)

> Sequenced for **value + dependencies**, single-maintainer + free/static throughout. Two
> **cross-cutting workstreams** run alongside (inserted per the critic): **(A) baseline/history
> backfill** — every measured promotion needs multi-year per-entity history for z/percentile/
> STL/PELT; backfill *precedes* P2 and P3. **(B) offline geoprocessing** — all heavy raster
> zonal-stats run **off** the weekly Action (precompute, commit only the scalar); no multi-GB
> GeoTIFF/NetCDF in CI, ever.

> **This is where the substrate is earned.** P0–P1 are not "prep for the globe" — they *are*
> the product (the correct, tier-stamped, lineage-complete store). The grand schema and the
> reasoning agent are downstream of them, not the starting point.

### P0 — Typed `LayerDescriptor` + mirrored registry  · _Month 0–1.5_ · effort L · ✅ **SHIPPED 2026-06-06 (PR #5)**
- **Goal:** make hub-and-spoke *structural* — and lay the substrate's foundation. Re-express the
  existing ~10 layers through one descriptor + authoritative Python registry, TS generated.
- **Build:** `registry/layers.py`; codegen for `types.ts`/`useData`/`LayerPanel`; the
  **import-graph firewall test lands here** (per critic, not P1).
- **Exit:** every current layer runs through the registry with **byte-identical** sidecars;
  `ENRICHERS`/hand-typed `LayerId` deleted; parity test green. _(Also fix the real orphan
  sidecars — `ships`/`disruptions`/`dwell`/`hazards`, not `gatun`/`weather`.)_
- **✅ Shipped:** `backend/freight_radar/registry/layers.py` — **22 `LayerDescriptor`s**, one source
  of truth; `enrich.ENRICHERS` + `publish._SIDECARS` now derived (byte-identical; the `dwell`
  orphan dropped — the registry's first reconciliation); `registry/codegen.py` →
  `frontend/src/lib/layers.gen.ts` drives the `LayerId` union, defaults, `LayerPanel` sections,
  and the `useData` fetch manifest (hand union + sections deleted). **Acceptance-harness Layers
  1–2 landed with it:** golden masters (11 deterministic sidecars frozen vs the hermetic dbt
  fixture, proving *no number moved*), the **structural import-graph firewall** (SIGNAL/CONTEXT
  can't reach the detector/ingest/WAP — with a teeth-check), registry parity (TS id-set == Python),
  and the **Python↔dbt stress-index parity** (`narrative/stress.py` == `mart_freight_stress_index`
  to the decimal across all 120 fixture days). The `feat/dbt-layer` work folded in as that parity
  gate. _Deviation from the sketch above: `useData` keeps its typed fetches (a registry **drift
  test** enforces the manifest) rather than being fully generated — preserves per-file types._

### P1 — Two-lane pipeline + CI honesty predicates + capability firewall  · _Month 1.5–3_ · effort L
- **Goal:** generalize WAP to N measured layers; make honesty machine-checked; land the
  **per-row bitemporal stamp** — tier + **valid-time** + **knowledge-time** + **grain** +
  `lineage_run_id` (the temporal model is the keystone, [§4](#4-architecture--the-typed-descriptor-the-unlock)). The **structural import-graph
  firewall is promoted from a line-item to THE gating invariant of the whole plan** — today it's
  a *comment* ("never reads the DB or writes flags"), not a test; with AI as a co-equal consumer
  the stakes rise, so the boundary must be a capability/import-graph **CI fact** before any agent
  ever reads the store.
- **Build:** per-layer WAP `CHECKS` + lineage; tier-scoped read-only ctx for CONTEXT;
  `source_manifest.yaml` (one validated row/layer: tier, url, license, auth, cost_class) gated
  by a pydantic model in CI; the **5 honesty suites** (tier predicates, causal-verb *lexicon*,
  import-graph firewall, freshness, zero-cost). **Causal-verb lint → advisory** (per critic);
  the structural firewall is the real guarantee.
- **Exit:** a deliberately-malicious branch (a CONTEXT layer writing `flags.json`) **fails CI**.

### P1.5 — The agent-legible *read* surface (export only — NOT reasoning)  · _Month 3_ · effort S–M
- **Goal:** make the store queryable by a machine **without building a reasoner** — the
  critic's key split: *substrate-for-agents* now, *the agent that reasons* much later.
- **Build:** one export step emits **both** the per-layer sidecars **and** a compact, read-only
  **Parquet/DuckDB export** of `fct_observation` + dims to Pages (queryable in-browser via
  **DuckDB-WASM**, zero marginal cost); plus a read-only **Standpoint Knowledge MCP server**
  (the generalization of the chat's `buildIndex()`) exposing `list_layers` / `get_facts` /
  `nearby` — every tool returns **facts-with-provenance**, there is **no write tool**.
- **Exit:** an agent (or the maintainer) can run cross-source SQL over the whole uniform store
  client-side; a test proves the MCP surface exposes no mutation; **no narrative agent exists
  yet.**

### P2 — Full ~2065-port measured spine + matrix-sharded refresh + lazy fetch  · _Month 3–4.5_ · effort L
- **Goal:** the single highest-impact measured extension — run the spine method across **all
  ~2065 PortWatch ports**, not just 28.
- **Build:** per-port owned scalar under generalized WAP; **per-domain FDR** (multiplicity
  control) so 2065 ports at `|z|≥3` don't manufacture flags; **matrix-shard the Action**
  (weekly spine / daily fast-context / on-demand) — *moved before the spine* (critic: the heavy
  spine must not breach the lock first); **manifest-gated lazy fetch** (toggling a layer fetches
  on demand) — tiling reserved for `snapshot.json` + 1–2 dense layers only; **grounded-chat
  re-architecture for lazy data** scheduled here (critic); **introduce `fct_observation` as the
  thin unifying index + the `dim_entity` crosswalk** (LOCODE/FIPS/H3/native-id → one
  `entity_key`) behind a **correctness gate, not a coverage gate** — they share the WAP audit
  machinery with the 2065-port extension, so the substrate spine and the data spine land
  together.
- **Exit:** all ~2065 ports carry our flags with FDR correction (UI states "tested N series,
  expect ≤k noise"); white-noise CI test holds; first-paint payload held flat; the crosswalk
  passes its correctness gate (known entity pairs resolve to one `entity_key`, zero silent
  mis-joins).

### P3 — Measured commodity / energy / macro signal cluster  · _Month 4.5–6_ · effort M–L
- **Goal:** the cleanest, highest-value **promotions** — raw observed input + a defensible
  Python anomaly we own.
- **Data:** World Bank Pink Sheet (keyless, ~70 commodities → our 12-mo rolling z); FRED
  **public-domain series only, by allowlist not comment** (per critic — no UMich/S&P/ICE
  proprietary); EIA, ENTSO-E, AGSI+; OECD CLI; Black Marble nightlights (offline zonal). **Each
  shows *our* anomaly, never the source price** (the price stays context — re-stating it as ours
  is authority-laundering).
- **Build:** one enricher per series-family; each enrolls in `multiplicity.py` FDR; each ships
  its own four-pack honesty tests + a numeric-correctness test.
- **Exit:** 6–8 measured signals live, each cleared all promotion gates; the board auto-gains a
  signals band.

### P4 — Context-ring breadth I: hazards · hydrology · conflict · infrastructure  · _Month 6–8_ · effort L
- **Goal:** broaden the cited-context ring across the natural-hazard, water, conflict, and
  infra domains; ship the **Layer Catalog + ⌘K palette + Source Ledger** (needed *before* the
  source count climbs).
- **Data (license-clean only):** EMSC seismic, GVP volcanoes, JTWC cyclones, geoBoundaries +
  Natural Earth basemap, USGS streamflow, GloFAS/GFMS floods, IODA + OONI internet outages,
  OpenSky/ADSB.lol flights, NOAA SWPC space weather. **Conflict → UCDP, not ACLED** (critic:
  ACLED bars commercial use; this is a portfolio piece). CC-BY-NC sources (TeleGeography,
  OpenSanctions, Cloudflare Radar, GPSJam, Global Fishing Watch) **flagged NC — caution**.
- **Build:** the catalog UI; an **upstream-drift detector** (a scheduled contract-check that
  pings the maintainer when a feed's schema/availability changes — the named-but-unbuilt
  mechanism, per critic).
- **Exit:** ~15–20 new context layers live + discoverable; daily+weekly shards run without
  holding the lock; drift detector green.

### P5 — Context-ring breadth II: human-impact + climate + presets/dashboards  · _Month 8–10_ · effort L
- **Goal:** complete the world-awareness footprint; make 50 layers navigable.
- **Data:** **offline-precomputed** exposure scalars (WorldPop/GHSL/WorldCover summed *inside*
  hazard footprints — **strictly "within-footprint", never "affected"/"impacted"**, lint-
  enforced); 1–2 proven climate rasters only (critic: cut Sentinel-5P L2 / 40-yr OISST — multi-
  GB, infeasible in-Action). **Migration → UNHCR, not IOM DTM** (DTM forbids derivatives).
  Curated **Lenses** (shareable layer+view+filter bundles) + per-domain dashboards (hydrology
  first — Gatún anchors it).
- **Build:** the offline geoprocessing toolchain (workstream B) hardened; exposure honesty
  tests; preset hashes.
- **Exit:** ~15 human-impact/climate layers live; exposure scalars pass within-footprint tests;
  lenses one-click load + share.

### P6 — The honest cross-layer surface **+ the reasoning agent** (the capstone, LAST)  · _Month 10–12_ · effort L
- **Goal:** the brand's two sharpest knives, built as the anti-centrum statement and the most
  honesty-hardened things in the project: a **proximity-only "Nearby" panel** + comparison
  matrix, and — fused here, **dead last** — the **DERIVED reasoning agent** that narrates over
  the substrate.
- **Build (surface):** `nearby.json` (CONTEXT-tier, `compute==passthrough`, `metric==null`): for
  a selected SPINE/SIGNAL entity, the CONTEXT items within a declared space/time window, ordered
  **only** by distance. The historical base-rate is **quarantined** — never rendered adjacent to
  a live flag (where "we never forecast" slips in the reader's head); a separate
  historical-archive view behind an interstitial, if at all.
- **Build (agent, DERIVED tier):** the reasoner gets a **read-only** connection to the store and
  may only **retrieve, group, summarize, and order cited facts by *declared neutral keys*** —
  time, distance, source, tier, freshness. It may **never** rank entities by risk, importance,
  severity, causal likelihood, evidence density, or predicted disruption (per review pass 2:
  "rank" silently becomes a risk score). It performs no arithmetic that invents a figure
  (ADR-0003 generalized). Every output is `{claim, tier:'DERIVED', cites:[lineage_run_ids],
  agent_model}` — **a claim with zero cites fails the grounding gate**, exactly as the chat does
  today. A shared **association-grammar lint** rejects `causes / drives / leads to / will /
  predicts / because-of` before surfacing; candidate relationships are emitted as fenced
  **HYPOTHESES routed to the G0–G5 promotion pipeline**, never stated as findings. **The agent
  reasons over everything (leverage) but every utterance is read-only, tier-stamped, cited,
  association-only, and physically downstream of — unable to mutate — the store (honesty).**
- **⚠ Two traps the critic flagged, both forbidden:** (1) **"rank by evidence density" is a risk
  score wearing a count's clothes** — "Hormuz 6, Panama 4, Suez 3" reads as a *risk ranking*; if
  ordering is shown it is a neutral roster of cited co-located receipts, not a leaderboard of
  "how much bad stuff is near you." (2) the agent must **never** render a historical co-occurrence
  rate next to a live flag.
- **Exit:** Nearby + matrix + the DERIVED agent live; CI proves `nearby.json` is CONTEXT-tier
  with no computed correlation, the agent surface has no write tool, and no fact table/enricher
  imports the `derived/` namespace (the AI firewall is structural, acyclic); the elevated weekly
  **Briefing** ships.

## 6. UI evolution

Surfaces, each arriving with the phase that earns it:

| Surface | Purpose | Arrives |
|---|---|---|
| **Globe** (kept) | The spine + toggleable context; the emotional anchor. | now |
| **Board** (widened) | Sortable analytical read of the spine; gains a signals band as promotions land. | now → P3 |
| **Layer Catalog + ⌘K palette** | The answer to "50 layers without clutter" — full-screen catalog + command palette over the registry. | P4 |
| **Active-layers tray** | The bottom-left panel becomes *manage* (what's on), not *discover*; `+ add (⌘K)` is the only always-visible entry. | P4 |
| **Presets / Lenses** | Named, shareable layer+view+filter bundles. | P4–P5 |
| **Per-domain dashboards** | When a domain crosses ~3 layers it earns a focused panel (hydrology first). | P5 |
| **Briefing** (elevated) | The once-a-week narrative read, standalone + linkable. | P6 |
| **Comparison / Co-occurrence** | Proximity-only comparator — the honesty-hardened knife, last. | P6 |
| **Agent lens** (Knowledge MCP + DERIVED layer) | A machine reads the *whole* uniform store (DuckDB-WASM in-browser, zero backend); its labeled, cited, association-only commentary renders as a distinct **DERIVED** layer. Read surface in P1.5; the *reasoner* last (P6). | P1.5 → P6 |
| **Source Ledger** | One public "show your work" page: every source, tier, cadence, license, last-fetched. | P4 |

**Navigation** scales via a three-layer model: *manage* (active-layers tray) in the persistent
UI; *discover* (⌘K catalog/palette) on demand; *recall* (saved/curated lenses). The
measured/context split + provenance rail stay legible because they're **registry-driven**, not
hand-written per layer.

## 7. Honesty-at-scale governance

**Generalized guardrails** (all registry-driven, all CI-gated):
1. **Causal/forecast-verb lexicon** — one shared list, advisory, applied to every layer's copy.
2. **Sidecar firewall** — structural (import-graph + capability object), not grep: CONTEXT
   physically cannot write a fact table or the detector.
3. **Multiplicity / FDR** — per **declared, frozen** domain family (the family definition is
   itself reviewed — it can launder honesty if gerrymandered); realized false-flag rate under
   injected white noise stays ≤ the family's declared budget.
4. **Temporal honesty (bitemporal)** — two clocks per fact (valid-time vs knowledge-time) + an
   explicit grain. Enforces three things in CI: **no fake-live** (freshness = `now − valid_time`,
   "N days old", never "now"); **no-hindsight history** (the replay filters to `knowledge_time ≤
   scrub_date`, showing values as known *then*, not post-revision); **grain discipline** (a join
   across grains without explicit resampling fails). Future valid-times are allowed **only** for a
   model layer's own output (e.g. GFS `f024`), never a freight forecast.
5. **Zero-marginal-cost gate** — `source_manifest` `cost_class==free`, `auth_model ∈
   {none, free_key, oauth_free}`; CI fails on a metered source.

**The CONTEXT → SIGNAL promotion pipeline** (six gates, each a CI artifact, the path Gatún
already walked): **G0** epistemic eligibility (inputs are raw observations, not a borrowed
forecast/score) → **G1** we compute a new Python scalar with a written method → **G2** self-
contained metric (not a function of the freight numbers) → **G3** proximity is association-only
→ **G4** no bridge into the spine/forecast → **G5** its own honesty tests + numeric-correctness.
Fail any gate → it stays context.

## 8. Metrics, milestones, risks

**Metrics:** layer count by tier (SPINE must stay **exactly 1**); honesty-CI pass rate;
promotion-gate throughput; false-discovery rate under white noise (≤ declared budget); freshness
integrity (all four timestamps); zero-cost compliance (100%); first-paint payload held flat as
layers grow; grounded-chat integrity (0 ungrounded, every fact tagged measured/context).

**Milestones:** M0 registry live · M1 honesty machine-checked · M2 full 2065-port spine +
scalable static app · M3 6–8 measured macro/energy signals · M4 hazard/hydro/conflict/infra ring
(~15–20) discoverable · M5 human-impact + climate ring + lenses · M6 Nearby + matrix + Briefing,
honest-by-construction.

**Top risks:** single-maintainer upkeep of ~50 free scrapers (→ the drift detector + a stated
*retirement* budget); the Nearby surface reading as causation (→ proximity-only + quarantined
base-rate); blocklist lint leakiness (→ structural firewall is the real guard); multiplicity
fabricating anomalies (→ FDR); the static-Pages + weekly-Action compute/`.git`-bloat ceiling
(→ matrix shards + a data-retention plan: a dedicated data branch / squash so daily sidecar
commits don't balloon history); lazy-fetch hurting snappiness (→ default-on budget + prefetch).

## 9. What the adversarial review changed

The critic's verdict: _"sound in its core thesis, overscoped in its back half, two unclosed
honesty holes. Ship P0–P3 with confidence; re-scope P4–P6 before committing tokens."_ Folded in
above:

- **Ordering fixes:** baseline/history backfill **before** P2/P3 (workstream A); matrix-sharding
  **before** the 2065-port spine; import-graph firewall in **P0**, not P1; an explicit offline-
  geoprocessing phase **before** P5's exposure rasters (workstream B).
- **De-scoped:** heavy rasters cut to 1–2 proven ones and moved **off** the Action (precompute
  offline, commit only the scalar); full tiling reserved for `snapshot.json` + 1–2 dense layers.
- **Honesty holes closed:** the Nearby **historical base-rate is quarantined** (never adjacent to
  a live flag); exposure wording is **"within-footprint", never "affected"**, lint-enforced;
  re-stating a source's own anomaly as ours is barred (G0).
- **Not actually free → dropped/swapped:** ACLED → **UCDP**; IOM DTM → **UNHCR**; FRED proprietary
  series → **public-domain allowlist**; CC-BY-NC sources (TeleGeography, OpenSanctions, Cloudflare
  Radar, GPSJam, GFW) flagged **NC-caution** for a commercial-adjacent portfolio. See the caveats
  section of [DATA-SOURCES.md](DATA-SOURCES.md).
- **New workstreams the plan had named but not built:** upstream-drift detector; cold-start
  backfill; grounded-chat scaling for lazy data; `.git`-bloat / data-retention; free-key rotation;
  an explicit **curation rubric** (an impact threshold + a stopping rule — "why these ~50 and not
  200").

## 10. The substrate reframe (north-star correction) — and its critic

A second pass reframed the whole vision (§1–§2, §4): **the product is the honest substrate; the
globe is its flagship *view*; AI agents are a co-equal consumer.** A human can't connect 93
datasets — an agent over a clean, tier-stamped, lineage-complete store can. And the honesty
brand is what makes the store worth more to a machine than a pile of CSVs. Folded in above; its
adversarial critic's load-bearing corrections:

- **Don't invert the build order.** The reframe is the right north star *and the reason P0–P1
  matter* — but the substrate's value is the boring 80% (the registry that **doesn't exist
  yet**, the firewall that's a **comment not a test**, crosswalk **correctness**, freshness as a
  hard gate). Start at the cathedral and you get "a beautiful empty `fct_observation` and a
  clever agent confidently citing a wrong-crosswalked, two-weeks-stale number in fluent
  association-free prose — **centrum with better manners**."
- **`fct_observation` is a *thin index*, not a giant schema.** "One optimal unified schema" is
  the **end state** of a multi-month refactor, not a thing to build up front. Per-layer sidecars
  stay the payload; the fact table is the join glue. Introduced in P2, not P0.
- **Separate the two "agents".** *Substrate-for-agents* (a read-only, correct, tier-stamped
  store + a Parquet/DuckDB-WASM lens + read-only MCP) is earned **now** → new **P1.5**. *The
  agent that reasons* is the **P6 capstone**, hardened like nothing else. Never let the second
  masquerade as the first.
- **New `DERIVED` tier** for agent commentary — read-only, `metric=null`, every claim cited,
  born in a quarantined `derived/` namespace, structurally unable to mutate the store or feed
  the detector (the CONTEXT firewall extended to AI; one-directional + acyclic, CI-proven).
- **The crosswalk is where the brand quietly dies** — `entity_key` resolution across 93 sources
  ships behind a **correctness gate, not a coverage gate**; a silent mis-join mis-attributes a
  number.
- **Two agent traps forbidden:** "rank by evidence density" is a **risk score in disguise**; and
  the agent may never render a historical co-occurrence rate next to a live flag.
- **Promote the structural firewall** from a P0/P1 line-item to **the gating invariant of the
  whole plan** — AI as a co-equal consumer raises the stakes from "CONTEXT can't write flags" to
  "nothing the reasoner emits can ever become a fact."

## 11. Review pass 2 — tightening before execution (incorporated)

A second external review. Its load-bearing message matches the critic's: _the biggest danger is
not bad design — it's overbuilding before the boring invariants are real._ Incorporated:

- **Minimum Viable Substrate (MVS) — the first real milestone, sharpening P0–P1.** A *smaller hard
  target*: layer registry + source manifest + lineage model + bitemporal timestamps + tier
  predicates + import firewall + deterministic sidecar export, **for the existing shipped layers,
  with no new datasets.** The **exit condition is a loop, not "architecture exists":** _a
  maintainer can add or modify one existing layer by editing one descriptor + one enricher, then
  CI proves tier, source, timestamp, lineage, firewall, and TypeScript parity._ The core unlock is
  that loop feeling **boring and safe**; everything else depends on it.
- **The crosswalk gets even more ceremony.** A bad crosswalk is *worse* than a missing layer —
  missing data is visible, **misjoined data looks authoritative.** P2 requires a **golden crosswalk
  suite** before scaling: hand-audited known pairs (PortWatch id ↔ LOCODE ↔ coords; chokepoint ↔
  geometry ↔ label; country ids across World Bank / OECD / EIA), **known _non_-joins** (look-alikes
  that must NOT merge), and ambiguous cases that must **require manual override.** The gate includes
  known non-joins, not just known joins — that's what stops fuzzy matching from becoming silent
  fabrication.
- **P2 is a pilot ladder, not a big jump:** registry+WAP generalized → 28 chokepoints migrated →
  **50-port pilot → 200-port pilot →** full ~2065. The *operational* issues (naming, missingness,
  churn, sparse histories, sidecar size, UI density, false-positive communication) surface before
  the statistical ones. And FDR needs **plain-language UX**, not jargon: _"Many ports are monitored
  at once, so a few unusual readings can occur by chance — Standpoint adjusts the flag threshold to
  reduce false alarms."_
- **P3: the SIGNAL bar stays brutal — signals are rare.** _"A SIGNAL is not 'important data' — it's
  a number whose method we are willing to own."_ Credibility rises if **most datasets stay CONTEXT.**
  (My refinement: keep the signal set **single-digit** for a long time, and capacity-bound P3 itself
  — 2–3 promotions first, not 6–8, same logic as P2's ladder.)
- **P4–P5 are menus, not commitments — capacity-bounded.** Ship the registry/catalog/drift
  machinery, then onboard the highest-value context layers **until the maintenance budget is full**
  — don't promise 15–20/phase. (My refinement: the capacity bound needs an actual **number** — a
  steady-state layer cap — treated as a hard ceiling, or "until full" is unmeasurable.)
- **Better success metric:** not _# layers live_ but **# layers still fresh, licensed,
  lineage-stamped, discoverable, and passing contract checks after 8 weeks.** Freshness-after-time
  beats launch count. (→ §8.)
- **Curation rule + retirement policy + deletion discipline.** Before a context layer is added it
  clears an explicit bar (relevance, license, cadence, coverage, provenance quality, maintenance
  burden, UI usefulness). A source that breaks repeatedly, changes license, goes stale, or fails
  attribution is **removed or frozen** — a serious data product needs deletion discipline.
- **Source Ledger → operational dashboard** (not just a transparency page): last fetched, last
  changed, freshness status, schema-contract status, license class, failure history. (Pairs with
  the drift detector.)
- **A tiny user-visible win baked into P0/P1.** Pure refactors are motivation-hostile; let the
  registry emit something visible even with no new data — the **auto-generated Source Ledger /
  layer catalog / provenance rail** — so the substrate work *feels* real.
- **Cap near-term ambition:** **P0–P3 is the committed roadmap; P4–P6 stay directional** until the
  substrate has survived production use.
- **The positive promise (was missing — the doc only says what it refuses to do).** Plain-language:
  _"A provenance-first world-state map for supply-chain disruption — measured freight stress, owned
  signals, cited context, and no fake causation. It shows what the world looked like, when we knew
  it, where it happened, and what evidence supports it."_ A one-pager (what · who-for · why-different
  · why-the-globe · why-the-substrate · what-ships-first) belongs up front.
- **THE PRIMARY-USER DECISION — resolved: don't narrow, keep it world-wide ("do it all").** The
  call: the product stays **honest world situational-awareness** (the substrate is, by definition,
  *every* free dataset) — it is **not** narrowed to a single analyst persona. The reviewer's
  anti-sprawl goal is met a *different* way: discipline comes from the **curation rule + the hard
  capacity cap + the retirement policy** above, **not** from a narrow audience. So "primary user"
  decides **sequence + default emphasis, not scope**: lead with the freight **SPINE** (it's built,
  and it's the most legible hook for any visitor — analyst, evaluator, or agent), then expand
  outward through the catalog in priority order. **Freight is the front door, not the ceiling.**
  "Do it all" = a long, gated, capacity-bounded march — never all-at-once; the cap + retirement are
  what make breadth survivable for a single maintainer.

---

_Execution note: P0 and P1 are pure refactors of what already ships — no new data, no
user-visible change — but they **earn the substrate**: they convert the honesty brand from prose
into a machine-checked invariant, which is what makes the store trustworthy enough to hand a
human eye **or an agent**. Start there. The grand schema and the reasoning agent are the most
exciting and the **least urgent** — they're downstream of, and must remain unable to corrupt,
the honest store. Build the boring 80% first._
