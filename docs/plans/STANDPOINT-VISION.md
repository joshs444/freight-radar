# Standpoint — The Year Vision

_A dependency-ordered, year-horizon plan to evolve Standpoint (the repo still slugged
`freight-radar`) from a ~10-layer ocean-freight globe into an **honest world
situational-awareness platform** — every relevant **free** data source on one globe + one
analytical board, toggled, cited, and read together._

Produced by a multi-agent research pass (5 data scouts → architecture / UI / governance
design → roadmap → an **adversarial critic**). The critic's corrections are folded into the
roadmap below and listed verbatim in [§9](#9-what-the-adversarial-review-changed). The full
source catalog is [DATA-SOURCES.md](DATA-SOURCES.md) (93 sources). **This is a map, not a
sprint** — we execute one shippable phase at a time, however long it takes.

---

## 1. North star

One globe + one board where every relevant **free** dataset is placed, toggled, cited, and
read together — with a **hub-and-spoke of ownership** that is **enforced by construction, not
by prose**. One measured **freight SPINE**, N self-owned measured **SIGNALS**, and a ring of
pure cited **CONTEXT**, scaled from ~10 layers to 50+ across a year **without ever asserting
causation between layers and without fabricating a forecast** — the deliberate opposite of
centrum-ai's "99.7% deterministic cascade."

The year's work makes the brand an **invariant**: a single typed `LayerDescriptor` registry
(Python authoritative, TS generated) where `kind ∈ {SPINE, SIGNAL, CONTEXT}` drives the
pipeline lane, the capability firewall, the CI honesty predicates, and every UI affordance —
so a layer that bridges into the freight detector **literally cannot merge.**

## 2. The honesty model, made structural

`measured` vs `context` is **epistemic — who computed the number** — not a ranking.

| Tier | Definition | Today |
|---|---|---|
| **SPINE** (exactly 1) | We own the *full chain*: ingest → fact tables → change-point detection → gated flags → the 0–100 stress index. Carries the product thesis ("disruption shows up in throughput weeks before the press"). | Ocean-freight throughput (28 chokepoints) |
| **SIGNAL** (small, vetted N) | We compute a defensible Python scalar over **raw observed** inputs and own the method. Stands alone; **never** wired into the spine or a forecast. | Gatún draft, business exposure/cost |
| **CONTEXT** (the broad ring) | Someone else's cited raw value shown as-is — fetched, filtered, geo-placed, labelled by us, but **not** transformed into a number we claim. "Possibly-related, not a stated cause." | GDELT news, USGS quakes, GDACS, storms, GFS wind, GIBS |

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

## 5. The roadmap (P0 → P6, ~12 months)

> Sequenced for **value + dependencies**, single-maintainer + free/static throughout. Two
> **cross-cutting workstreams** run alongside (inserted per the critic): **(A) baseline/history
> backfill** — every measured promotion needs multi-year per-entity history for z/percentile/
> STL/PELT; backfill *precedes* P2 and P3. **(B) offline geoprocessing** — all heavy raster
> zonal-stats run **off** the weekly Action (precompute, commit only the scalar); no multi-GB
> GeoTIFF/NetCDF in CI, ever.

### P0 — Typed `LayerDescriptor` + mirrored registry  · _Month 0–1.5_ · effort L
- **Goal:** make hub-and-spoke *structural*. Re-express the existing ~10 layers through one
  descriptor + authoritative Python registry, TS generated.
- **Build:** `registry/layers.py`; codegen for `types.ts`/`useData`/`LayerPanel`; the
  **import-graph firewall test lands here** (per critic, not P1).
- **Exit:** every current layer runs through the registry with **byte-identical** sidecars;
  `ENRICHERS`/hand-typed `LayerId` deleted; parity test green. _(Also fix the real orphan
  sidecars — `ships`/`disruptions`/`dwell`/`hazards`, not `gatun`/`weather`.)_

### P1 — Two-lane pipeline + CI honesty predicates + capability firewall  · _Month 1.5–3_ · effort L
- **Goal:** generalize WAP to N measured layers; make honesty machine-checked.
- **Build:** per-layer WAP `CHECKS` + lineage; tier-scoped read-only ctx for CONTEXT;
  `source_manifest.yaml` (one validated row/layer: tier, url, license, auth, cost_class) gated
  by a pydantic model in CI; the **5 honesty suites** (tier predicates, causal-verb *lexicon*,
  import-graph firewall, freshness, zero-cost). **Causal-verb lint → advisory** (per critic);
  the structural firewall is the real guarantee.
- **Exit:** a deliberately-malicious branch (a CONTEXT layer writing `flags.json`) **fails CI**.

### P2 — Full ~2065-port measured spine + matrix-sharded refresh + lazy fetch  · _Month 3–4.5_ · effort L
- **Goal:** the single highest-impact measured extension — run the spine method across **all
  ~2065 PortWatch ports**, not just 28.
- **Build:** per-port owned scalar under generalized WAP; **per-domain FDR** (multiplicity
  control) so 2065 ports at `|z|≥3` don't manufacture flags; **matrix-shard the Action**
  (weekly spine / daily fast-context / on-demand) — *moved before the spine* (critic: the heavy
  spine must not breach the lock first); **manifest-gated lazy fetch** (toggling a layer fetches
  on demand) — tiling reserved for `snapshot.json` + 1–2 dense layers only; **grounded-chat
  re-architecture for lazy data** scheduled here (critic).
- **Exit:** all ~2065 ports carry our flags with FDR correction (UI states "tested N series,
  expect ≤k noise"); white-noise CI test holds; first-paint payload held flat.

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

### P6 — The honest cross-layer surface (deliberately LAST)  · _Month 10–12_ · effort L
- **Goal:** the brand's sharpest knife, built as the anti-centrum statement: a **proximity-only
  "Nearby" panel** + comparison matrix that show co-location/co-timing and **stop** — no
  coefficient, no lag, no "drives".
- **Build:** `nearby.json` (itself CONTEXT-tier, `compute==passthrough`, `metric==null`): for a
  selected SPINE/SIGNAL entity, the set of CONTEXT items within a declared space/time window,
  ordered **only** by distance. **Per critic — the historical base-rate is quarantined:** it is
  **never rendered adjacent to a live flag** (that's where "we never forecast" slips in the
  reader's head); if shown at all, only in a separate historical-archive view behind an
  interstitial.
- **Exit:** Nearby + matrix live, proximity-only, no-causation stamp; CI proves `nearby.json` is
  CONTEXT-tier and contains no computed correlation; the elevated weekly **Briefing** ships.

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
4. **No-fake-live** — four timestamps per layer (`source_observed_at ≤ fetched_at ≤
   generated_at`), UI reads "N days old (cited)", never "now".
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

---

_Execution note: P0 and P1 are pure refactors of what already ships — no new data, no user-
visible change — but they convert the honesty brand from prose into a machine-checked invariant,
which is what makes the other five phases safe to build. Start there._
