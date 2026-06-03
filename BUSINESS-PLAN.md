# Freight Radar — Business Intelligence + News Expansion Plan

A second living layer on the honest globe: every auto-flagged disruption now answers **"what does this cost *me*, and who else is reporting it?"** — an **additive, component-visible Cost-of-Disruption stack** computed in Python from the user's own trade lanes, plus **cited, dated, possibly-related news** attached per area. Same spine as v1: numbers traced to source × user input × a visible assumption; estimates labelled estimates; never a claim that a headline *caused* a z-score.

**Where we start:** business-impact **v1 already ships** — `exposure.py` maps active flags → lanes, sums value/TEU, writes a `business` block per flag + a portfolio `exposure.json`, and `DataFeed.jsx` renders it labelled "ESTIMATE." We **extend** that contract; we do not rewrite it. v1 has three honest-debt items this plan pays down: (1) the value-at-risk formula `value × delay/365` silently assumes a **100%/yr carrying rate** (~4× overstatement); (2) port matching is **exact-string** against PortWatch display names and silently zeroes on any real CSV; (3) the whole enrichment runs **only in the static `publish.py` path** — the durable Temporal loop never calls it, so the always-on snapshot ships flags with no `business` block and a stale `exposure.json`. News enrichment is **greenfield** (no file, no contract, no activity).

---

## The architectural seam (how business + news flow into the existing pipeline)

The app still reads **ONLY local DuckDB tables + static JSON**. Two new enrichment stages slot **between detect and assemble**, in *both* code paths, sharing one implementation:

```
fetch → compute_and_detect → llm_attribute → ENRICH_BUSINESS → ENRICH_NEWS → assemble_snapshot → publish
                                              (wraps exposure.py)  (news.py + WebSearch, gated+cached)
```

- **Business** stays a **post-hoc mutation** of the loaded `flags.json` (a `business` block) + the portfolio `exposure.json` sidecar — the existing pattern. The 19-key `Flag` contract and `FLAG_KEYS` filter in `run_detection.py` are **untouched**; nothing is added to the detector contract.
- **News** is a **separate `news.json` sidecar keyed by `flag_id`** (never stuffed into the Flag), loaded optionally in `useData.js` with `.catch(()=>null)` exactly like `exposure.json` — a static deploy with no news still renders.
- **Temporal parity** is the load-bearing fix: `enrich_business` *wraps* `exposure.enrich_from_files` (already pure/idempotent — no logic duplicated) and `enrich_news` is a new gated/cached activity. The manifest gains `has_business` / `has_news` booleans so `/api/health` and the frontend can show which enrichments are present.
- **Cost discipline:** news uses **Claude Code WebSearch + free RSS/GDELT/PortWatch corroboration only** — no paid news API. WebSearch is **enrichment prose only**; the deterministic fetcher owns every citation, gated behind the same `flag_id` ledger `llm_attribute` already uses (a `meta_news` table), so a re-run does **zero** web searches.

---

## Data contracts (extend, never rewrite)

### Trade-flow CSV — `business_flows_v2.csv` (backward compatible)
`schema_version` header. v1 columns still load; new columns default sensibly and **lower the confidence band** when absent (the honesty gradient is a feature).

**Required core (tiny — anyone can fill it):**
`lane_id` · `direction`(import|export) · a resolvable port pair: **`origin_locode`/`dest_locode` (preferred)** OR `origin_port`+`origin_country`(ISO3) / `dest_port`+`dest_country` · **≥1 of** `annual_value_usd` / `annual_teu` (bulk lanes have value, 0 TEU).

**Optional standards-keyed (stored verbatim, format-validated, never blocking):**
`origin_region`/`dest_region` (user grouping label only) · `hs6`(`/^\d{6}$/`) · `hs_national`(opaque) · `item_category` (human label, derivable from HS2) · `incoterm`(11 Incoterms 2020 enum) · `incoterm_named_place` · `mode`(UN/CEFACT Rec.19 digit, default 1=maritime) · `lead_time_days` · `ships_per_year` · `transit_days` · `unit_value` · `avg_daily_demand` · `demand_stddev` · `service_level`(→Z) · `po_cogs` · `carrying_rate` · opaque local-only `supplier_name`/`po_number` (**never echoed to any published JSON or WebSearch**).

**Optional time granularity:** long-form `month`(1–12) rows OR wide `value_m01..value_m12`. Present → exposure computed against the **disrupted flag's month**; absent → `annual/12` **labelled "even-spread estimate."**

### Per-flag `business` block (additive to v1)
v1 keys kept; the headline quantity is **fixed and re-labelled**:
```jsonc
{
  "exposed_value_usd": 4200000,          // FACT: sum of user value on hit lanes (+ Incoterm freight note)
  "exposed_teu": 310, "lane_count": 4, "exposed_lanes": [...], "top_items": [...],
  "est_delay_days": {"low": 8, "expected": 12, "high": 16},   // band, not a point
  "delay_basis": "reroute_table:Suez=10-14d [src]",            // method shown
  "route_known": true, "routing_confidence": "modeled|fallback|none",
  "matched_by": "locode|portid|name|unmatched",
  "working_capital_tied_up_usd": {"low": ..., "expected": ..., "high": ...},  // CCC reframe of v1 gross prorate
  "added_inventory_days": 12,
  "cost_of_disruption": {                 // additive, component-visible, mutually-exclusive mitigation paths shown
    "carrying_cost_of_delay_usd": {"low":..,"expected":..,"high":..},   // value × carrying_rate × delay/365
    "reroute_premium_usd": {...},          // exposed_teu × $/TEU (Suez/BAM/Cape only; 0 elsewhere)
    "safety_stock_burn_usd": {...},        // Z·σ·(√(LT+delay)−√LT)·unit_value·rate (softest line)
    "otif_penalty_exposure_usd": {...},    // at_risk_PO_COGS × 3% (only when delay exits window)
    "expedite_ceiling_usd": {...},         // air − ocean $/kg = UPPER BOUND on rational spend
    "total": {"low":.., "expected":.., "high":..},
    "method": [{"line":"carrying_cost_of_delay","formula":"...","inputs":{...},"sources":["..."]}, ...]
  }
}
```
v1's `value_at_risk_usd` is **redefined and renamed**: `carrying_cost_of_delay_usd` carries the corrected `× carrying_rate` factor; the raw gross prorate survives only as the honestly-labelled `working_capital_tied_up_usd` (capital **locked**, not lost).

### `news.json` sidecar (NEW — keyed by `flag_id`)
```jsonc
{ "generated_at": "...", "search_date": "2026-06-03", "window_days": 7,
  "items": { "<flag_id>": {
    "items": [ {"title","url","source","published":"YYYY-MM-DD","tier":"official|trade_press|newswire|aggregator","via":"google_news_rss|gdelt|rss:gcaptain|websearch"} ],
    "corroboration": { "portwatch_disruption": {"eventname","eventtype","severitytext","fromdate","todate"} | null, "outlet_count": 3 },
    "fetched_at": "...", "relation": "possibly_related",
    "disclaimer": "Headlines co-occurring in time and place. Not a confirmed cause of this anomaly." } } }
```

### `exposure.json` (additive)
Add `lanes_with_known_route` / `total_lanes` coverage pair, `active_news_cited` count, and per-component portfolio bands (low/expected/high). Round hard (`$2.0–2.6M`, never `$2,057,535`).

---

## Waves

### Wave B1 — Fix the existing number + band it (one-line credibility win) · ~1–2 days
**Goal:** stop the ~4× carrying-cost overstatement and the false-precision point estimate before anything is built on top.
**Deliverables:**
- `exposure.py`: change line 125 to `exposed_value × CARRYING_RATE × delay/365` (`CARRYING_RATE` default `0.25`, configurable; source: 20–30%/yr industry); **rename** `value_at_risk_usd` → `carrying_cost_of_delay_usd`. Add `working_capital_tied_up_usd` (the old gross prorate, honestly relabelled) + `added_inventory_days`.
- Replace point estimates with `{low, expected, high}` bands everywhere (carrying rate 20/25/30%; delay from a `est_delay_days` band, not a scalar). Round hard in the UI.
- A cross-check: also compute `value_of_time_per_day` via Hummels-Schaur **0.6–2.3%/day ad-valorem** and surface both, reconciled.
- `exposure.json` + `DataFeed.jsx` copy: headline becomes **"estimated cost-of-delay: $X–$Z (expected $Y)"** with a confidence chip; the v1 tile keeps degrading-gracefully.
**DoD (receipt):** run the static path on the committed sample; `exposure.json` shows the **new field names + a band whose `expected` is ~25% of the old point figure**, and `DataFeed.jsx` renders a range not `$2,057,535`. A snapshot/golden test pins the corrected math.

### Wave B2 — Portid/LOCODE port resolution + coverage-aware routing · ~2–3 days
**Goal:** kill the silent-zero failure modes — exact-name matching *and* the empty-on-unlisted-pair routing dict.
**Deliverables:**
- `business/port_resolver.py` built against the **ports DATABASE layer** (has LOCODE/lat-lon/industry — *not* the daily fact layer): (1) LOCODE exact → `confidence 1.0, method=locode`; (2) normalized name **within user ISO3** + alias table (Saigon→HCMC, Pudong→Shanghai) → `0.6–0.95, name+country`; (3) below threshold → **`unresolved`, surfaced, never guessed**. Persist a cached override map (correct each port once). Bundle a trimmed LOCODE→portid lookup from the layer the app already ingests — no third-party gazetteer.
- `business_flows_v2.csv` + `samples/business_flows_v2.csv` golden; header-alias map (POL/POD/"Port of Loading"). Match on `portid` first, name last; emit per-flow `matched_by`.
- Coverage-aware routing: add a **default/fallback** so an unlisted region pair doesn't read as zero; emit `route_known` / `routing_confidence` per lane; branch **Suez vs Cape** when a `cape_reroute` flag is active. Document each corridor's assumed path string for the UI.
- `exposure.json` gains `lanes_with_known_route`/`total_lanes`.
**DoD (receipt):** a CLI prints per-row resolution; on the golden v2 CSV **100% of lanes resolve by `locode`** and on a deliberately-messy CSV ("Port of LA","Shanghai") the resolver reports `name+country` confidences + any `unresolved` — **no silent zeros**. A routing-coverage test asserts every sample lane is either modeled or explicitly `unmatched`.

### Wave B3 — The Cost-of-Disruption stack (additive, component-visible, banded) · ~3–4 days
**Goal:** five individually-sourced, toggleable cost lines per flag with a "show your work" panel — out-honest the SCRM vendors by exposing every input.
**Deliverables:**
- In `exposure.py`, compute the five lines from the contract above: `carrying_cost_of_delay` · `reroute_premium` (default **$200–400/TEU** Suez/BAM/Cape, 0 elsewhere) · `safety_stock_burn` (Z 90/95/99%=1.28/1.65/2.33; **labelled softest**, wide band on defaults) · `otif_penalty_exposure` (**3% of at-risk PO COGS**, Walmart-cited, only when delay exits the order window) · `expedite_ceiling` (air − ocean $/kg = **upper bound / sanity cap**).
- **Anti-double-count:** treat carrying-vs-reroute-vs-expedite as **mutually-exclusive mitigation scenarios**; render the cheapest path and the components — never a bare additive total.
- Delay derived from the signal where possible: ports scale delay from the flag's existing `zscore`/`pct_change` into a median/P90 band; chokepoints keep the cited reroute table, banded by source confidence (Cape 10–14d well-supported; small straits widened).
- Optional `hs6`-driven **secondary `criticality_weighted_value_usd`** *alongside* (never replacing) the plain figure.
- A **`method[]` panel** per line in the JSON → a "Show your work" UI accordion in `DataFeed.jsx`: formula + exact inputs + a citation for every constant.
**DoD (receipt):** a flag's `business.cost_of_disruption` renders five labelled lines, each with formula+inputs+source in the UI; a test asserts the total equals the **cheapest mitigation path** (not the naive sum) and that `safety_stock_burn` carries the widest band when demand inputs are defaulted.

### Wave N1 — Honest news fetcher + PortWatch corroboration (deterministic, cited) · ~3–4 days
**Goal:** attach real, dated, entity-matched, possibly-related news — citation owned by a deterministic fetcher that cannot hallucinate.
**Deliverables:**
- `business/news.py` (sibling to `exposure.py`): **PortWatch `disruptions_database` corroboration first** (flag entity ∈ `affectedports` OR haversine <~50km AND window overlap `[fromdate,todate]`) — highest-trust, needs no causal hedge (same dataset's producer). Then **Google News RSS** (`?q="{entity}" when:{N}d`), **GDELT DOC 2.0** (`near20:"{entity}"`, JSON, keyless), **trade-press RSS** (gCaptain/Splash247/Maritime Executive, filtered by entity), official notices (Panama/Suez Authority, USCG) as top tier.
- **Hard gating:** attach an item only if resolvable URL **+** parseable date **+** date ∈ `[as_of−window, as_of+2d]` **+** curated-entity/alias match. Toponym mitigation: entity + maritime context term (`(port OR shipping OR vessel OR container)`); prefer domain feeds. Dedup via URL-canonicalization + SimHash on titles → count **distinct outlets** (`outlet_count`); cap to top 3–5 by `credibility_weight(tier) × exp(−Δdays/τ)`. Zero qualify → `items:[]` (still show corroboration). Never write/infer a headline or date; never quote a paywalled body. Handle the `cape_reroute` synthetic-portid (chokepoint-vs-port entity split).
- Write `news.json`; `useData.js` optional load; `DataFeed.jsx` renders under each brief as **"Possibly related coverage (not a confirmed cause)"**, *after* the computed metric, with tier badges + dates + `outlet_count`; PortWatch hits labelled distinctly **"Corroborated by IMF PortWatch disruption: <eventname>."**
**DoD (receipt):** run on live flags — at least one active flag shows ≥1 **real dated cited** item with a clickable publisher URL within the window, the disclaimer + `relation:possibly_related` present, and a flag with no qualifying news honestly shows the empty state. A test asserts the honesty invariant: **every non-empty news item has a non-null URL and parseable date**, and `relation`/`disclaimer` are present.

### Wave N2 — Wire both into the durable Temporal loop (close the divergence) · ~2 days
**Goal:** make business + news first-class durable activities so the always-on snapshot stops shipping bare flags.
**Deliverables:**
- Two new activities in `FreightRadarWorkflow`: `enrich_business` (**wraps** `exposure.enrich_from_files` — no duplicated routing logic) and `enrich_news`; sequence becomes `…→ llm_attribute → enrich_business → enrich_news → assemble_snapshot → publish`.
- `enrich_news` gated by a new **`meta_news` DuckDB table** (mirrors `meta_attribution`): `flag_id PK, searched_at, items_json` — fetch/WebSearch only for `lifecycle ∈ {new, escalated}`; identical re-run = **0 searches / 0 WebSearch**. Optional top-N-critical WebSearch pass adds one plain-English summary line, every claim mapping to a fetched URL.
- Manifest + `/api/health` gain `has_business` / `has_news`.
**DoD (receipt):** `docker-compose up`; the **published** `flags.json` from the durable loop now contains `business` blocks and a fresh `news.json` exists (a contract test that would currently FAIL now passes). A `test_news_dedup_free_rerun` proves a second identical run issues **zero** web searches. Kill-worker-mid-run → restart → enrichment resumes without re-searching.

### Wave P — VP-grade framing + portfolio polish · ~2 days
**Goal:** speak the procurement-VP's language and make the honesty visible, not just claimed.
**Deliverables:**
- Working-capital / **CCC translation** surfaced at flag + portfolio level: "this disruption adds ~X inventory days / ~$Y working capital tied up" (DIO/cash-to-cash vocabulary), and a one-line **TTR-vs-TTS resilience read** (`TTR_proxy` = est disruption duration vs `TTS_proxy` = days-of-inventory, when supplied) — shortfall flagged when `TTR > TTS`.
- `exposure.json` coverage tile ("X of N lanes modeled," `active_news_cited`); confidence chips everywhere; the honesty gradient explained ("richer CSV inputs → narrower bands").
- README section: **"How the business + news layer stays honest"** (see below); a hero showing a flag with its banded cost stack + a dated cited headline.
**DoD (receipt):** the deployed demo shows, on a real flag, a banded cost-of-delay range, a "Show your work" panel with cited constants, a CCC line, and a dated "possibly related" headline — and the README's honesty section maps 1:1 to enforced behavior.

---

## How it stays honest (enforced, not asserted)

1. **Numbers in Python, prose in the LLM.** Every dollar = `source figure × user input × visible assumption`; WebSearch/LLM may never alter a computed number (the v1/Wave-5 invariant). The "Show your work" panel prints the formula, inputs, and a citation for every constant (carrying rate, $/TEU, OTIF 3%, Hummels-Schaur per-day).
2. **Bands, not points.** Headline is always **"estimated cost-of-delay: $X–$Z (expected $Y)"** with a confidence chip; figures rounded hard. No `$2,057,535`.
3. **Locked ≠ lost.** `working_capital_tied_up` is labelled a CCC/inventory-days effect (capital locked), distinct from the small carrying-cost-of-delay; lost value only on spoilage/true lost sales (separate, lowest-confidence lines).
4. **No double-counting.** Reroute / expedite / delay-carrying are **mutually-exclusive mitigation scenarios**; `expedite_ceiling` caps the rest.
5. **The honesty gradient is a feature.** Sparse CSV → wider bands + explicit "illustrative, replace with your terms"; `safety_stock`/OTIF lines flagged softest on defaults.
6. **Coverage is visible.** `matched_by` + `route_known` + `lanes_with_known_route/total_lanes` — an unlisted lane reads as **unmatched**, never a silent zero.
7. **News is co-occurrence, never cause.** Citation owned by a deterministic fetcher (resolvable URL + parseable date + in-window + entity-matched); `relation:possibly_related` + disclaimer always present; the number leads, news follows; PortWatch's own `disruptions_database` is the one cross-check that needs no hedge. No fabricated/undated/paywalled-body citations; `outlet_count` (distinct outlets) is the corroboration signal — article volume never drives severity.
8. **Zero marginal cost.** WebSearch + free RSS/GDELT/PortWatch only; gated by `meta_news` so re-runs cost nothing. Opaque PO/supplier fields stay client-side, never published or searched.