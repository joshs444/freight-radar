# Provenance & Connection — Standpoint Plan

> **Status: ✅ EXECUTED 2026-06-08 — the full P0 → P2 roadmap shipped + deployed the same
> day.** Commits: `c3d8809` (P0-A) · `4b449d6` (P0-B) · `6cef3f4` (P1-A) · `6c600b4` (P1-D)
> · `dc5099c` (P1-B) · `781cb04` (P1-C) · `58d6ad3` (P2-A) · `c9bfbe4` (P2-B) · `a912462`
> (fence #8: nearby.ts fallbacks routed through the catalog). **P2-C (multi-flag stories)
> deliberately not built** — the plan itself flags it the highest-risk, most-cuttable item.
> All claims below verified against the real data files and components on 2026-06-08.

## 1. Vision

Make **"click any datapoint → see its raw input → the computation we ran → the published number → the cited source (linked)"** a *single invariant* fed from the registry SSOT, rendered identically on flags, unflagged ports/chokepoints, globe context dots, the cross-domain signals, and the AI brief. On top of that, make honest **triangulation** legible: when several *place-attributable* cited receipts sit near the same point (the maritime measurement + sampled ships + that flag's own news/storm/official event + co-located quakes/hazards within a radius+window), show them as one "what's near here" roster — while national/global signals (truckload rate, Brent, metals, macro, slack, labor) live in a structurally-**fenced** "system context — not this place" band that can never be attributed to the point. Co-location is association, never causation, at every layer.

## 2. What we have today

Strongest pieces already shipped — build on them, do not replace:

- **Flag provenance trace (the just-shipped surface).** `DataFeed.tsx` `Provenance` component (lines 448-472) renders, on an expanded flag, a real trace: tier (`measured · computed in Python`), `from <source ↗>` (linked), `method:`, `metric:`, `as of <date>`. Backed by data — `flags.json` carries `source/method/metric/as_of/value/baseline/pct_change` on all **168** flags. **Gap in the data:** 0/168 carry `source_url`; the link is resolved at render time by a **17-entry regex** in `lib/provenance.ts` that pattern-matches the free-text `source` string — a parallel URL map that can silently drift from the registry SSOT.
- **Context dots deep-link OUT.** `Globe.tsx` onClick for news/quakes/EONET/tides/streamflow/hazards each `window.open(item.url)` to the canonical source (USGS eventpage, NASA event, the article, GDACS report). Per-item `url` verified present. They trace OUT but never UP to the layer's tier/license/honesty-note.
- **The triangulation primitive already exists.** `lib/nearby.ts` `computeNearby()` gathers every cited CONTEXT item (quakes/news/EONET/marine/tides/streamflow/hazards) within a radius of a selected port/chokepoint, **distance-only**, each row linked to its source + carrying the `ASSOCIATION_ONLY` disclaimer. Wired live at `App.tsx:469` (`NearbyPanel`) and into the Board. `nearbyFamilyCounts` (nearby.ts:169-172) **deliberately refuses to sum families into one number** ("a single nearby total is a risk score wearing a count's clothes") — the right anti-leaderboard instinct, already encoded.
- **The Source Ledger is the canonical "show your work" surface.** `SourceLedger.tsx` already `fetch()`es `data/store/catalog.json` at runtime (line 103), declares `Source{url,license}` + a TIER label map, and renders kind/source/license/honesty_note per layer. Its `fr-brief-derived` view shows per-claim `<code>` cite tokens and links named news sources to articles via `news.json` (claimRow, lines 225-253).
- **The registry is the verified SSOT.** `backend/freight_radar/registry/layers.py` → `catalog.json`: every layer carries typed `Source(name,url,license)` + kind/tier + metric + honesty_note + `derives_from`. **Verified:** flags/ports/chokepoints all have `source: null` + `derives_from: "snapshot"` (only `snapshot` carries `Source(name="IMF PortWatch", url="https://portwatch.imf.org", license="PortWatch terms")`); `freight_rate` carries `source/source_url/license/method`.
- **Per-family signal sidecars carry the full chain.** `freight_rate.json` (and the 5 other family files) carry file-level `source/source_url/method/disclaimer/as_of` + a **36-point computed `z_series`** per item — the entire raw→computed→published→cited chain.
- **The offline reasoner is already gated.** `derived/reason.py` `_connections` joins each measured flag to its co-occurring per-flag cited news as **association** (`flag_id`+`cites`+`section` stamped per claim); `ground_or_abstain` drops any claim the store can't cite; `gate_briefing` fails closed on causal/forecast language. Surfacing those claims inherits the gate — the UI re-authors nothing.

### Where provenance is missing today (verified)

| Surface | State |
|---|---|
| Flag | Trace exists; URL via brittle regex, not registry; flat 4-span, not a stepped chain |
| **Cross-domain signals** (`SignalBoard.tsx`) | **No trace at all.** `signal_pool.py` (lines 49-59) emits only `{family,id,name,unit,as_of,value,our_zscore,fdr_significant}` and **drops** source/source_url/method/z_series. Verified: `signals_fdr.json` items have **8 keys, 0 source, 0 source_url, 0 z_series, 0 lat/lon**. The richest *measured* tier is the *only* one a user cannot click to trace. |
| Unflagged ports/chokepoints | Hover tooltip only; click falls through to bare `<type> · monitored` (`DataFeed.tsx:435-441`). Most-clicked thing on the globe, traces to nothing. |
| Context dots | Trace OUT (deep link) but never UP (tier/license/honesty-note). Marine has **no per-item url** (`nearby.ts:95` returns `null`; Globe marine layer has no onClick). |
| Feed brief (`BriefCard.tsx`) | Renders text+note+footer; **ignores `brief.json`'s per-bullet `cites`** (verified: bullets carry `cites` 6/6, no per-bullet chips rendered). The fully-cited version lives only in `SourceLedger`. |

## 3. The honest connection model

### The boundary: place-specific vs system-level

Two structurally-separated zones in any per-place panel — the separation *is* the product.

**ZONE 1 — "Here, specifically" (place-attributable evidence).** Only things with a real location at/near this point:
- the maritime **measurement** for THIS entity (PortWatch),
- **sampled ships** nearby,
- this flag's **own** news (`news.json` keyed by `flag_id`), `live_storm`, `official_event`,
- `computeNearby`'s co-located quakes/EONET/marine/tides/streamflow/hazards within the radius+window.

Each row links to its cited source and carries the `ASSOCIATION_ONLY` disclaimer.

**ZONE 2 — "System context — national/global, not this place" (fenced).** The cross-domain signals (`freight_rate`, `commodities`, `metals`, `macro`, `slack`, `labor`) — **verified 0/34 carry lat/lon**. They get their own in-place trace (source link + method + z-series sparkline) but are *never* distance-tagged, *never* counted into Zone 1, *never* given a globe dot.

### FINAL recommendation on national signals in the place panel

**Adopt option (a) — fenced + labeled — as the default**, and make the fence load-bearing.

- **Reject (b) "show only when reinforcing the local move."** Deciding a national signal "reinforces this place" is an implicit directional/causal claim — the exact thing the brand forbids. Show the full significant set regardless of sign, or none. Never a sign-matched subset.
- **Reject (c) "keep out entirely"** *as the default* — it abandons the user's explicit "connect everything" goal. **BUT** (per the adversarial pass) (c)'s *spirit* has real merit and is the recommended **lighter alternative if the fence proves insufficient in testing**: keep the national set in the always-visible, non-place-scoped `SignalBoard` (where it is honestly global), and put only a single neutral pointer in the place panel ("see cross-domain signals →"). That still "connects everything" — the signals are one click away — without ever rendering national numbers under a place's name.

### Honesty fences from the adversarial pass (non-negotiable)

These are the design's hardest-won constraints. They are *machine-checkable* where noted — encode them, don't promise them.

1. **The national band must be place-INVARIANT.** Its content AND order must be a pure function of the global `signals_fdr.json`, **byte-identical across every place panel**. Any place-conditioned sort/emphasis/sub-selection (e.g. bolding energy signals when an oil chokepoint is selected) silently *becomes* rejected option (b). → **Acceptance test, not a code-review promise** (see P2-B).
2. **No single "converging" / "N sources" count — ever.** The adversarial pass is explicit: a "5 cited sources converging" headline (a) asserts the five point at ONE phenomenon (co-location ≠ corroboration — a quake 740 km away is not corroboration), (b) co-counts a MEASURED anomaly with CITED context as if independent confirmations, and (c) reintroduces exactly the summed risk-number `nearbyFamilyCounts` already refuses to build. → Keep families **separate and unsummed**; replace "converging" with non-claiming language ("also within 750 km · co-located, association only"); **never co-count a measurement with context items**; and make the radius's arbitrariness visible (the same place "has" 1 receipt at 500 km and 9 at 1500 km — a count that triples with a radius toggle is not evidence).
3. **De-dupe one real-world event across feeds.** One cyclone can appear as the flag's `live_storm` chip AND a GDACS hazard row AND a GDELT news dot AND an EONET event — four *feeds*, one *event*. Distinct feeds is not distinct evidence. Group them visibly ("same storm — GDACS + EONET + GDELT"); never let one event increment any tally more than once.
4. **Ports ≠ chokepoints — different trace shapes.** **Verified:** snapshot **ports (2065)** carry `{vessels (annual), portcalls, cargo_mix, share_import/export}` — **no `pct_change`, no `n_total`, no baseline**; only the **28 chokepoints** carry `pct_change/n_total/baseline`. So an unflagged PORT's trace may honestly say only "**annual vessel count**, IMF PortWatch, as of {date}" — a **cited count, NOT "computed in Python", NOT a z-score, NO "% vs 28d".** Reusing the snapshot layer's chokepoint metric string under a port would mislabel a static count as a computed anomaly (cited-as-measured error).
5. **Split RAW (cited) from COMPUTED (ours) on signals.** The z-score is OURS; FRED publishes the raw PPI, not the anomaly (registry honesty_note layers.py: "We compute the z-score anomaly; the index stays cited context"). The signal trace must read "RAW: BLS PPI, cited from FRED ↗ (public domain) → COMPUTED BY US: 12-mo rolling z = +4.84" — **never collapse to "from FRED" on the z-score line** (that attributes our anomaly to FRED).
6. **Resolve effective source by walking `derives_from` to the root, but resolve TIER per-layer.** flags/ports/chokepoints all `derives_from: snapshot` → walk to get the IMF PortWatch URL. But a chokepoint's `pct_change` IS computed (z-score) while a port's `vessels/yr` is a raw count — **same root source, different tier.** One centralized, unit-tested `effectiveSource(layerId)` helper; tier is *not* inherited from the root.
7. **Multi-flag "stories" are a browsing grouping, never a causal container.** The detectors fire per-entity; nothing in `flags.json` establishes a common cause (0/168 carry region/corridor/cause). "3 ports in Yemen carrying disruption flags this week" (descriptive) is honest; "Yemen crisis spreading" is not. If shipped: explicitly frame as "flags that share a country — grouped for browsing, not a shared cause", **no per-cluster narrative/summary line, no inter-cluster ranking, never reuse reason.py's single-flag prose template for a multi-flag synthesis.** This is the highest-risk, most-cuttable proposal.
8. **Provenance flows FROM the registry, never re-hardcoded.** Replace `lib/provenance.ts`'s 17-entry URL regex. Also route `nearby.ts`'s hard-coded `?? 'USGS'` / `?? 'GDELT'` / `?? 'Open-Meteo'` fallbacks (lines 66-119) through the same catalog lookup — or the triangulation hero ships with the same drift the provenance work is meant to kill.

## 4. Roadmap

Build order by value/effort (feasibility-confirmed): **P0-A → P0-B → P1-A → P1-D → P1-B → P1-C → P2-A → P2-B**, with multi-flag stories as a frontend-only fast-follow. Every backend change here re-derives from the **local** DuckDB + already-written sidecars (no PortWatch refetch, no multi-year backfill).

### P0 — Provenance plumbing (highest leverage-per-line; unblocks everything)

**P0-A — Carry signal provenance through `signal_pool.py`.** *(effort: S)*
- **What:** Widen the projection at `signal_pool.py` lines 49-59 to carry `source`, `source_url`, `method` (read **once per family** from the sidecar's file-level keys — they're per-file, not per-item), the per-item `z_series` (36-pt), and a `fenced: true` marker. Add the same fields to `SignalItem` in `types.ts` (mandatory, currently missing). Then give `SignalBoard.tsx` a per-row expandable trace via the new `<Trace>` (P1-A): tier `measured · z computed in Python`, "RAW: <index> cited from <source ↗>" then "COMPUTED BY US: z = …" (fence #5), the `z_series` as a `Sparkline` (drop-in, `Sparkline({values})`), as_of.
- **Why:** The richest *measured* tier is the *only* one with no trace, and the fix is the cheapest in the audit. Regenerates **standalone** via `signal_pool.write(data_dir)` — zero network; `test_signal_pool.py` already covers the projection over real files. Stamps `fenced=national` that P2-A's band needs.
- **Files:** `backend/freight_radar/signal_pool.py`, `frontend/src/components/SignalBoard.tsx`, `frontend/src/components/Sparkline.tsx`, `frontend/src/types.ts`, (regen) `frontend/public/data/signals_fdr.json`.

**P0-B — Stamp `source_url` + `license` onto flags from the registry; retire the regex.** *(effort: M)*
- **What:** The flag SOURCE is hard-coded in TWO spots (`detect/detectors.py:48`, `export_snapshot.py:33`). Replace both with the registry-resolved root Source — for flags, walk `derives_from` to `snapshot` → `registry.by_id("snapshot").source` (the FLAGS layer's own source is `None`, verified). Add `source_url` + `license` to `FLAG_KEYS` (`run_detection.py`:55-58) so `flags.json` carries them on all 168. Add `source_url` + `license` to the `Flag` interface in `types.ts` (currently missing — mandatory). Regenerate `flags.json` from the **local** `data/freight_radar.duckdb` (no network). **Delete** the 17-entry `SOURCE_URLS` regex in `lib/provenance.ts` *only after* every surface reads `flag.source_url`.
- **Why:** Kills the single biggest honesty risk in the provenance layer (a client-side URL map that can fork from the SSOT) and unblocks the unflagged-port trace (P1-B).
- **Files:** `backend/freight_radar/detect/detectors.py`, `export_snapshot.py`, `detect/run_detection.py`, `frontend/src/lib/provenance.ts`, `frontend/src/types.ts`, (regen) `frontend/public/data/flags.json`.
- **Caveat (adversarial #9):** Stamping a URL into 168 flags + 34 signals freezes it at build time; a stale shipped data file could disagree with a regenerated `catalog.json`. **Mitigation:** make P2-B a **deploy-gate** (fail the weekly refresh Action if any stamped url ≠ registry), so stale data can never ship. The data is regenerated weekly with the catalog, so the two stay in lock-step — provided the gate runs on the deploy artifact.

### P1 — One trace primitive + apply it everywhere

**P1-A — Build ONE registry-fed `<Trace>` primitive (the stepped chain).** *(effort: M)*
- **What:** `frontend/src/components/Trace.tsx` with the canonical schema `<Trace layerId? source sourceUrl license tier method metric raw computed published asOf series? honestyNote? fenced? />`. Renders the **4-step chain**, not 4 sibling spans: RAW → COMPUTATION → PUBLISHED NUMBER → CITED SOURCE (linked, licensed, dated). For a flag: `PortWatch AIS port-calls → 28-day baseline vs pre-shift norm → 5.67 vs 75.01/day = −92% → IMF PortWatch ↗ (PortWatch terms, 2026-03-01)`. Add a one-shot `catalog.json` fetch to `useData.ts` (required — only `SourceLedger` fetches it today, locally). Provide a single unit-tested `effectiveSource(layerId)` helper that **walks `derives_from` to the root** for the URL but resolves **tier per-layer** (fence #6). Refactor `DataFeed.tsx` `Provenance` (448-472) to render `<Trace>`; feed it into SignalBoard (P0-A), the globe-dot cards (P1-C), unflagged ports (P1-B), and BriefCard (P1-D). `lib/provenance.ts` shrinks to just `sourceName()`.
- **Why:** The structural root cause of uneven provenance is 5 ad-hoc renderers, none reading the registry at runtime. One primitive fed from `catalog.json` makes "honest provenance at the point, everywhere" a single invariant. Most of it is an extract from `SourceLedger` (which already declares `Source{url,license}` + the TIER map), not greenfield.
- **Files:** `frontend/src/components/Trace.tsx` (new), `DataFeed.tsx`, `lib/provenance.ts`, `lib/useData.ts`, `components/SourceLedger.tsx` (extract types), `frontend/public/data/store/catalog.json` (read).

**P1-D — Bring per-claim cites + article links into `BriefCard`.** *(effort: S, cite-chips half; M for article links)*
- **What:** **Cite-chips half (in scope now):** `brief.json` bullets already carry `cites` (verified 6/6) which `BriefCard.tsx` (82-94) ignores — render them as small `<Trace>`-style chips per bullet. Pure render add, no new fetch. **Article-link half (requires care):** the `flag_id` that links named news → `news.json` articles lives **only** on `ai_briefing.json` connection claims (verified 3/8 carry `flag_id`), **NOT** on `brief.json` bullets (0/6). So article links require BriefCard to also consume `ai_briefing.json` AND **keep the two tiers visually distinct** — `brief.json` is the deterministic template; `ai_briefing.json` is "what an AI said" and must be labeled as such (adversarial #8: do not fold reasoner claims into the deterministic hero brief silently). **Recommendation:** ship cite-chips first; defer article-links until `flag_id` is carried into `brief.json`'s connection bullets (a small backend add in `reason.py`/the brief builder), OR render them in a clearly-labeled DERIVED sub-block.
- **Why:** The brief a casual user actually reads is the *least*-traced surface; the most-traced is buried in the Board. The cite-chips win is free; the article-link logic already exists in `SourceLedger:225-253`.
- **Files:** `frontend/src/components/BriefCard.tsx`, `SourceLedger.tsx` (lift `claimRow`), `backend/freight_radar/derived/reason.py` (only if carrying `flag_id` into `brief.json`).

**P1-B — Unflagged ports & chokepoints get a measured trace — with the correct, different shapes.** *(effort: S)*
- **What:** Render `<Trace>` in `DataFeed.tsx`'s unflagged branch (435-441) from the snapshot source stamped in P0-B. **CRITICAL (adversarial #5):** ports and chokepoints are DIFFERENT shapes. A **chokepoint** (28, carry `pct_change/n_total/baseline`) gets the computed trace: "PortWatch AIS → per-chokepoint throughput vs baseline → n_total/day, +X% vs 28d → IMF PortWatch ↗". A **port** (2065, carry only annual `vessels`) gets a **cited-count** trace only: "annual vessel count → IMF PortWatch ↗, as of {date}" — **no z-score, no "% vs 28d", no "computed in Python".** Do **not** reuse the snapshot layer's chokepoint metric string under a port.
- **Why:** Closes the most-clicked-thing gap with honesty parity (a flag is just a detected anomaly on the same measured series) — *without* fabricating a computation ports don't have.
- **Files:** `frontend/src/components/DataFeed.tsx`, `Trace.tsx`, `frontend/public/data/snapshot.json` (read).

**P1-C — Context dots: trace UP (in-app card) before they trace OUT.** *(effort: M)*
- **What:** Replace each `window.open(item.url)` in `Globe.tsx` (news/quakes/EONET/tides/streamflow/hazards) with: select the dot → open a lightweight in-app `<Trace>` card (reuse NearbyPanel row styling) showing the cited value as-published, the layer's tier `cited · context` + `honesty_note` from `catalog.json`, THEN the "open source ↗" deep link. Keep hover = tooltip, click = trace card (a deliberate hover-vs-click contract). **Marine gap:** `nearby.ts:95` returns `url=null` and `marine.json` has no per-item url — surface the **file-level** Open-Meteo source + CC-BY license in the card (no per-item link possible). **Cleanup:** the GDACS URL builder is duplicated verbatim (`Globe.tsx:382-383` and `nearby.ts:125-128`) — centralize it.
- **Why:** A user clicking a quake dot is thrown off-site without ever seeing "this is CONTEXT · USGS · public domain · association only." The dot should say WHAT it is before sending you away.
- **Files:** `frontend/src/Globe.tsx`, `lib/nearby.ts`, `Trace.tsx`.

### P2 — Honest connection / triangulation

**P2-A — "What's near here": fold flag-attached evidence into NearbyPanel + the fenced national band.** *(effort: L)*
- **What:** Upgrade `NearbyPanel.tsx` (at `App.tsx:469`, fed by `computeNearby`) into the two-zone view from §3. **Zone 1** merges the place-specific evidence that today renders as separate stacked blocks in `DataFeed.tsx:431-434` (per-flag news / `live_storm` / `official_event`) INTO the `computeNearby` roster, each row a `<Trace>`. **Zone 2** is the fenced "System context — national/global, not this place" band consuming P0-A's `fenced=national` signals (pure presentation). **Honesty (fences #2/#3):** NO single "converging" count — a family-separated, **de-duped** (one event ≠ N feeds), distance-only, tier-labeled roster; never sum, never severity-sort, never co-count a measurement with context. **MCP parity (feasibility):** the backend mirror `store.nearby()` (`store.py:240`, uses the same distance-only families, no flag-news join today) must get the SAME fold-in so the agent surface tells the identical story — this doubles the surface vs a frontend-only reshuffle.
- **Why:** The user's literal ask ("connect everything"). The primitive exists; the gap is synthesis (fold-in) + the load-bearing fence.
- **Files:** `frontend/src/components/NearbyPanel.tsx`, `lib/nearby.ts`, `App.tsx`, `DataFeed.tsx`, `frontend/public/data/news.json`, **and** `backend/freight_radar/store.py` (parity).

**P2-B — Registry-parity acceptance test + deploy-gate.** *(effort: S)*
- **What:** Slots into the existing harness (`backend/tests/test_registry_codegen.py`, `test_golden_sidecars.py`, `dbt/ci/check_parity.py`). Assert: (1) every `flag.source_url`/`license` == the registry-resolved **root** Source (walk `derives_from` to `snapshot`) — assert against `registry.by_id(...).source`, **NOT** `catalog.json` (which emits `source: null` for flags → false pass); (2) every `signals_fdr` item's `source_url` == its family layer's registry Source.url; (3) **the national band is place-invariant** — its content+order is a pure function of the global file (fence #1). Run it as a **deploy-gate** in the weekly refresh Action so stale stamped data can never ship (adversarial #9).
- **Why:** Provenance honesty is the brand; a stamped URL that silently diverges from the SSOT is exactly what P0-B removes the regex to prevent. Cheap insurance fitting the established acceptance-harness philosophy.
- **Files:** `backend/tests/` (new test), `backend/freight_radar/registry/layers.py` (read), `frontend/public/data/{flags,signals_fdr}.json` (read).

**P2-C (fast-follow, frontend-only) — Multi-flag "stories" as a browsing grouping.** *(effort: L; OPTIONAL — highest risk)*
- **What:** Cluster active flags by an **observable** shared key (resolve `flag.portid → snapshot port.country`, verified 2065/2065; corridor adjacency via `haversineKm`) — `flags.json` has no country field (0/168) but the join is client-side, no regen. Render each cluster as a story card listing member flags (linked to their place panels) with their measured `pct_change` + cited source. **Honesty (fence #7):** explicitly framed as "flags that share a country — grouped for browsing, not a shared cause"; **no per-cluster narrative line, no inter-cluster ranking, no reused causal prose.** Strongly consider **cutting** — it is the proposal furthest from the data's support and most likely to produce a confident regional lie.
- **Files:** `frontend/src/lib/nearby.ts` (haversine), `DataFeed.tsx`, `hooks/useMonitorModel.ts`, `frontend/public/data/snapshot.json` (read).

## 5. First 3 changes (shortlist)

1. **P0-A — widen `signal_pool.py`'s projection** (≈10 backend lines + `SignalItem` type) to carry `source/source_url/method/z_series/fenced`. Regenerate `signals_fdr.json` standalone via `signal_pool.write()` (no network). Turns the richest measured tier from un-traceable chips into the best-traced points on the site, and stamps the `fenced=national` flag everything downstream needs.
2. **P0-B — stamp `source_url` + `license` onto flags from the registry** (replace the two hard-coded `SOURCE` literals with the `derives_from`→snapshot root Source; add to `FLAG_KEYS` + the `Flag` type; regenerate `flags.json` from the local DuckDB), then delete the `lib/provenance.ts` regex once every surface reads `flag.source_url`.
3. **P1-A — build the one `<Trace>` primitive** (stepped raw→computed→published→cited chain, fed from a runtime-fetched `catalog.json` via a unit-tested `effectiveSource(layerId)` that walks `derives_from` for URL but resolves tier per-layer) and refactor the flag `Provenance` + SignalBoard onto it. This is the reusable unit every later surface (P1-B/C/D, P2-A) consumes.
