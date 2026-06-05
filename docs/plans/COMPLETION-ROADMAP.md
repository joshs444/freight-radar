# Freight Radar — Completion Roadmap

_Single source of truth for what is built vs. what is left. Reconciles PLAN.md (8 waves), BUSINESS-PLAN.md (B1/B2/B3/N1/N2/P), and DATA-LAYERS-PLAN.md (W0–W5) against the real code at `/Users/joshspadaro/dev/freight-radar` as of 2026-06-03. Skeptical, evidence-backed; prior "done" claims were re-verified, not trusted._

---

## 1. Where it really stands

The **core product is genuinely real and shipping**: the PortWatch→DuckDB pipeline, the light 3D globe, the detection brain (STL+z+PELT+persistent-level-shift, which correctly surfaces the Strait of Hormuz collapse as `chokepoint_persistent_collapse`), per-entity sparklines + trend reads, business-impact v1, cited news v1, and the market layer (live Stooq quotes) all render end-to-end on a static GitHub Pages site. Detection is **reproducible** (re-running the detectors yields the exact 5 committed flags), and the Wave 0 enricher registry genuinely **closed the static-vs-Temporal divergence** — both `publish_static` and the Temporal `enrich` step call the identical `run_enrichers`. That's a credible portfolio core.

But the gap between the framing and the substance is wider than the prior claims suggest. **The "durable agent" has never actually run against the real DB** — there is no `meta_attribution` ledger table in `data/freight_radar.duckdb`, proving every committed sidecar came from the manual static path, and the Temporal loop is only ever exercised in an in-memory time-skipping test harness (no docker, no `:7233`). **Production never self-refreshes** — CI only builds the frontend from committed JSON; `ships.json` already lags the latest tick by 3.5 hours (13:14 vs 16:44), so freshness silently rots after deploy. The **LLM attributor is a pass-through stub** (no model is ever called). The three BUSINESS-PLAN credibility fixes (**B1 carrying-cost, B2 LOCODE routing, B3 cost stack**) are **untouched** — the headline `value_at_risk_usd = value*delay/365` overstatement (~4x) is **live in the committed data**. And the four things Josh most wants — **the chat, weather, dwell, official corroboration, and a weekly "what's going on" narrative** — are essentially **greenfield**. Roughly: PLAN.md done, DATA-LAYERS ~33% done (W0/W1 of 6), BUSINESS-PLAN ~30% done (N1 core + N2 wiring only).

---

## 2. Status table — every wave / feature

| Plan | Wave / Feature | Status | Evidence | Gap if partial |
|---|---|---|---|---|
| PLAN | W0 PortWatch→DuckDB plumbing | ✅ Done | `ingest/`, `storage/db.py`, contract test; DB 28MB, as_of 2026-05-31 | — |
| PLAN | W1 Globe + snapshot + issues rail | ✅ Done | `Globe.jsx`, `snapshot.json` (28 chokepoints + 2065 ports), 10 lanes | — |
| PLAN | W2 Detection brain (STL+z + briefs) | ✅ Done | `detect/`, flags carry zscore/baseline/brief_md; reproducible 5 flags | — |
| PLAN | W3 Durable Temporal loop | ⚠️ Partial | `workflow.py`/`activities.py`/`schedule.py` exist, 10 tests pass | **Never run live** — no `meta_attribution` table in real DB; proven only in time-skipping harness, never docker/`:7233` |
| PLAN | W4 Time-scrubber replay | ⚠️ Partial | `TimeScrubber.jsx` drives globe replay (choke glow + which flags fired) | **Globe-only** — does NOT re-drive feed rows/sparklines/exposure/news/market to scrubbed date |
| PLAN | W5 CUSUM+PELT, Cape-reroute, lifecycle, holidays, persistent | ✅ Done | `detect/changepoint.py`, `cape_reroute.py`, `persistent.py`; Hormuz collapse surfaces | — |
| PLAN | W6 Live-AIS garnish + trails | ✅ Done (garnish tier) | `ais_consumer.py` standalone, `ships.json` → TripsLayer; explicitly non-load-bearing | — |
| PLAN | W7 Polish + portfolio framing + Pages deploy | ✅ Done | README, Pages workflow, light-theme redesign | (README has stale "dark basemap" line — see §3) |
| BUSINESS | B1 Fix carrying-cost + band it | ❌ Not started | `exposure.py:125` still `round(value*delay/365)`; field still `value_at_risk_usd`; no bands | The flagged ~4x overstatement ships live ($3.13M portfolio sum; Hormuz $1.07M vs $267K at 0.25 rate) |
| BUSINESS | B2 LOCODE/portid resolution + coverage-aware routing | ❌ Not started | `business_flows.csv` is v1 (region/port strings); no `port_resolver.py`; exact-string match at `exposure.py:94` | Silent-zero on any real CSV; no Suez-vs-Cape branch; no routing_confidence |
| BUSINESS | B3 Cost-of-Disruption stack (5 banded lines) | ❌ Not started | grep `cost_of_disruption`/`carrying_cost_of_delay` = 0 hits | No reroute_premium / safety_stock / otif / expedite; no method panel; no "show your work" |
| BUSINESS | N1 Honest news fetcher | ⚠️ Partial | `news.py` real Google News RSS, cited, gated, disclaimered; `news.json` 12.6KB | No PortWatch-disruption corroboration, no GDELT, no trade-press RSS, no tier badges, no SimHash (dedups title[:60] only) |
| BUSINESS | N2 Wire business+news into Temporal | ⚠️ Partial | Enrich step runs all sidecars every tick (the divergence fix) | No `meta_news` dedup ledger (re-fetches RSS every tick); no named `has_business`/`has_news` booleans |
| BUSINESS | P VP-grade framing / honesty section | ⚠️ Partial | Layers coverage tile + disclaimer chips; light redesign shipped | No CCC/working-capital line, no TTR-vs-TTS, no "X of N lanes modeled" coverage; README isn't the P honesty section (no banded stack to frame) |
| DATA | W0 Un-orphan enrichers / registry | ✅ Done | `enrich.py` ENRICHERS=[exposure,news,timeseries,market]; both drivers call `run_enrichers`; `test_enrich.py` | — |
| DATA | W1 Market impact → market.json | ✅ Done | `market.py` (Stooq), live Brent 98.08, per-flag linked blocks, `MarketBlock` renders | — |
| DATA | W2 Internal signals + IMF official-events + spillovers → disruptions.json | ❌ Not started | manifest `disruptions: present:false`; no `internal.py`/`ingest/disruptions.py`; no `official_event` on any flag | The Hormuz official-corroboration receipt Josh wants does not exist |
| DATA | W3 Weather/storms → weather.json | ❌ Not started | manifest `weather: present:false`; no NHC/GDACS fetch, no cone matcher; "weather" only a manifest-stub string | No globe cone overlay, no weather chip |
| DATA | W4 AIS-computed dwell → dwell.json | ❌ Not started | manifest `dwell: present:false`; `ais_consumer.py` is decorative garnish only ("never read by flag engine") | No geofences, no dwell tables, no `port_dwell_spike` detector |
| DATA | W5 Ask-Freight-Radar chat | ❌ Not started | No `Chat.jsx`, no `lib/ask.js`, no `/api/chat`; grep chat/ask = 0 | The capstone — entirely greenfield |
| — | Weekly narrative brief ("what's moving this week") | ❌ Not started | Not in any plan; no digest/narrative code | The other thing Josh explicitly wants; closest is per-flag trend+news, no roll-up |
| — | Global stress index / momentum analytics | ❌ Not started | `trend.js` is per-entity only; no portfolio rollup | No 0–100 index, no % chokepoints disrupted, no WoW delta |
| — | User CSV upload UX | ❌ Not started | Trade data only from `samples/business_flows.csv` / env var, read server-side | "Your trade data" framing is a static demo; no client upload exists |
| — | Production self-refresh / freshness | ❌ Not started | `deploy.yml` only `npm build`; `ships.json` lags tick 3.5h | Data goes stale silently after deploy; no cron regen |

---

## 3. Claimed but not actually wired — fix these first

These are overstatements where the framing outruns the code. Cheap to correct and they restore credibility:

1. **"Durable Temporal agent auto-flags" — never run against the real DB.** No `meta_attribution` ledger table exists in `data/freight_radar.duckdb` (tables: dim_chokepoint, dim_port, fct_chokepoint_daily, fct_port_daily, fct_flags, meta_ingest_runs, meta_source_status). That table is written only by the live `llm_attribute` activity, so the always-on loop has **never executed**; all committed sidecars came from the manual static path. Durability is proven only in an in-memory time-skipping harness. **Fix:** either actually run the docker-compose loop once and commit the receipt, or soften the README to "durable loop (verified in test harness; static publish path drives production)."

2. **"LLM attribution / Ollama polish" — it's a pass-through stub.** `activities.py` `_Attributor.attribute()` returns `brief_md` unchanged and just increments a counter. No model is called; all prose is template-only. (Honest in code comments, but the README/PLAN framing implies real LLM polish, and there is no existing LLM client for a chat Tier-2 to reuse.) **Fix:** state plainly that prose is deterministic-template (this is actually a strength — lean into it).

3. **BUSINESS-PLAN's own value-at-risk fix is not in the shipped code.** `exposure.py:125` is verbatim `round(value * delay / 365)`, field still named `value_at_risk_usd`, no carrying rate, no bands. The ~4x-overstated number ships live in both `flags.json` and `exposure.json` (portfolio $3,126,028). **Fix = B1 below** (one-line, ~1–2h).

4. **"Your trade data" exposure framing implies an upload path that doesn't exist.** UI says "Your exposure · your trade data" / "No exposure in your trade data," but the value is a pre-baked backend `exposure.json` from a sample CSV. On Pages, every visitor sees only Josh's sample. **Fix:** either relabel as "sample trade data" or build the upload (item E).

5. **`manifest.json` layer-freshness metadata is consumed by nothing in the frontend.** The per-layer present/kb/generated_at (and weather/dwell/disruptions present:false) are computed but never fetched in `src/` — only `snapshot.as_of` is shown. **Fix:** surface a small coverage/freshness strip (cheap, see Polish).

6. **README stale "dark basemap" line.** `README.md:70` says "token-free CARTO **dark** basemap," contradicting the light redesign and README lines 3/21. **Fix:** one-line edit.

7. **No production freshness mechanism (gap in all three plans).** CI never runs `publish_static`; nothing regenerates sidecars on a schedule. `ships.json` (13:14) already lags the latest tick (16:44). Market is intraday-stamped but rots silently after deploy. **Fix:** scheduled regen (see Polish/deploy — Josh has CronCreate).

---

## 4. Remaining work — prioritized, grouped roadmap

Effort: S ≈ ≤1d · M ≈ 1–3d · L ≈ 3–5d. Value: High/Med. All items are **free/keyless** unless noted.

### [Finish the pipes] — close the integrity gaps before adding surface area
| # | Item | Effort | Value | Cost | Definition of Done |
|---|---|---|---|---|---|
| P1 | Run the durable loop live once (docker-compose up → real tick → `meta_attribution` written) OR soften README framing | S | High | Free | Either a real-tick receipt with the ledger table committed, or README no longer claims an always-on agent it can't show |
| P2 | Production self-refresh: scheduled `publish_static` + commit (CronCreate) so sidecars don't rot | M | High | Free | Cron regenerates + commits all sidecars on a cadence; `ships.json` generated_at no longer lags the tick |
| P3 | Fold `ais_consumer --demo` into the publish/loop so `ships.json` refreshes with the pipeline | S | Med | Free | `ships.json` generated_at matches the rest of the tick |
| P4 | `meta_news` (and market) dedup ledger so identical re-runs = 0 web fetches | M | Med | Free | A `test_*_dedup_free_rerun` asserts re-tick triggers 0 outbound fetches when inputs unchanged |
| P5 | Staleness-regression test: a real tick's published `news.json`/`market.json` have newer generated_at than prior | S | Med | Free | Test fails if a sidecar ships stale |

### [Business depth: B1–B3] — the credibility fixes (do B1 immediately)
| # | Item | Effort | Value | Cost | Definition of Done |
|---|---|---|---|---|---|
| B1 | Fix carrying-cost + band it: `value*CARRYING_RATE*delay/365` (rate 0.25), rename → `carrying_cost_of_delay_usd`, add `{low,expected,high}` + `working_capital_tied_up_usd` | S | High | Free | Hormuz drops $1.07M→~$267K; field renamed; frontend reads new name; test asserts the band |
| B2 | LOCODE/portid resolution + coverage-aware routing: `port_resolver.py`, `business_flows_v2.csv` (LOCODE+ISO3), `matched_by`/`routing_confidence`, Suez-vs-Cape branch on cape_reroute, `lanes_with_known_route` in exposure.json | M | High | Free | A real-world CSV no longer silently zeroes; coverage line "X of N lanes modeled" renders |
| B3 | Cost-of-Disruption stack: 5 banded lines (carrying / reroute_premium / safety_stock_burn / otif_penalty / expedite_ceiling), anti-double-count total, `method[]`, "Show your work" accordion in DataFeed | L | High | Free | Each flag shows a banded cost stack with a sourced method panel; total ≠ naive sum |

### [Data layers: official / weather / dwell]
| # | Item | Effort | Value | Cost | Definition of Done |
|---|---|---|---|---|---|
| D-W2 | Internal signals + **IMF official-event corroboration** + spillovers → disruptions.json; `flag.official_event` chip | L | High | Free | Hormuz flag carries an `official_event` corroboration; `<OfficialEvent>` chip renders; manifest disruptions present:true |
| D-W3 | Weather/storms → weather.json (NHC CurrentStorms/GDACS, cone two-gate spatial+temporal matcher), globe cone overlay + chip | L | Med | Free | A live storm cone overlaps a chokepoint → weather chip on that flag; manifest weather present:true |
| D-W4 | AIS-computed port dwell → dwell.json (geofences, per-vessel state machine, `port_dwell_spike` detector) | L | Med | Free | A dwell spike produces a flag/sidecar; manifest dwell present:true; caveat-swap from "garnish" to "signal" |

### [The Chat] — Ask Freight Radar (Tier-1 is the real shippable product)
| # | Item | Effort | Value | Cost | Definition of Done |
|---|---|---|---|---|---|
| C1 | **Tier-1 client-side grounded Q&A** (`lib/ask.js` + `Chat.jsx`) over already-loaded sidecars: in-browser index keyed by entity + alias map; intents: what's going on with `<entity>` / biggest risk / what's worse-vs-improving / am I exposed to `<port>` / what changed this week / why is Brent up / how bad vs normal. **Every numeric token must exist in a source JSON (honesty test).** Suggested-question chips | L | High | Free | Works on Pages today, no backend; chips prefill; answers cite the JSON value; no invented numbers |
| C2 | (Optional, non-prod-default) Tier-2 LLM `/api/chat` on EC2 FastAPI; prefer local Ollama | M | Med | **Ollama free; Claude API metered (flag)** | Runs only on the EC2 stack; Pages still falls back to Tier-1; metered path clearly gated |

### [Narrative & trends] — the "what's going on this week" layer Josh wants
| # | Item | Effort | Value | Cost | Definition of Done |
|---|---|---|---|---|---|
| N-Brief | **Weekly/daily auto-narrative brief** → `brief.json`: deterministic 3–5 cited bullets assembled at publish time from flags+market+news+exposure (numbers in Python, never invented), with a "this week" diff (new flags since last ISO week, escalations, resolutions). Render as a hero card above the feed | M | High | Free | A hero brief renders with real, source-traceable bullets; regenerates each tick; week-window diff works |
| N-Stress | **Global Ocean Freight Stress Index (0–100)** in `stress.json`: severity-weighted by economic weight, % of 28 chokepoints disrupted, lifecycle counts, recomputed historically from timeseries for a 30/90d sparkline + WoW momentum ("fastest-deteriorating", "most-improved"). Top-of-page gauge | M | High | Free | A single index number + trend sparkline + momentum chip render at top, all computed from existing series |
| N-Events | Append-only `events.json` timeline (flag born/escalated/resolved) the brief can cite | S | Med | Free | Scrollable "what happened" log renders; brief cites it |

### [User data upload] — turns the demo into a tool
| # | Item | Effort | Value | Cost | Definition of Done |
|---|---|---|---|---|---|
| U1 | **In-browser CSV upload**: drag-drop → papaparse → port the exposure/routing math to JS → recompute business blocks + portfolio exposure entirely client-side ("your data never leaves your browser"). Template CSV + "try sample data" button | L | High | Free | A visitor's own CSV produces their own exposure on Pages, nothing uploaded; privacy line shown |
| U2 | Scenario "what-if" slider on the user's lanes ("if Suez stays shut 30 more days…") — cheap once U1 exists | S | Med | Free | Slider re-drives the client-side exposure model live |

### [Polish / deploy / README / UX]
| # | Item | Effort | Value | Cost | Definition of Done |
|---|---|---|---|---|---|
| X1 | Fix the §3 framing leaks: README dark-basemap line, surface `manifest` layer-freshness coverage strip, relabel/keep "your trade data" honest | S | High | Free | README accurate; coverage/freshness visible in UI |
| X2 | Make the time-scrubber re-drive the feed panel (rows/sparklines/exposure/news/market follow the scrubbed date) | M | Med | Free | Scrubbing the past updates the right panel, not just the globe |
| X3 | Deep-link/URL state (selected entity + filter + scrub time in URL hash) → shareable views | S | Med | Free | A shared URL reopens the same entity/filter/time |
| X4 | Entity search box (find one of 2065 ports by name) | S | Med | Free | Type-ahead jumps to a named port/chokepoint |
| X5 | Onboarding empty-state + "how it stays honest" inline panel | S | Med | Free | First-visit explainer; stranger gets it in ~10s |
| X6 | Genuine mobile/responsive pass beyond the single 820px stacking rule | M | Med | Free | Scrubber + brief/market/news blocks usable on a phone |
| X7 | Watchlist (localStorage) + browser notification on new/escalated flag for watched entities | M | Med | Free | "Watch" persists; notifies on change vs last-seen manifest |
| X8 | Weekly email digest (Temporal/cron + Gmail MCP) + `feed.xml` RSS sidecar of new flags | M | Med | **Free** (Josh's Gmail/cron) | An emailed weekly digest sends; RSS validates |
| X9 | Export/share: "download this week's brief as PDF/PNG", export exposure CSV | S | Med | Free | Brief exports; exposure CSV downloads |

---

## 5. Recommended build order

Fix the credibility leaks first (cheap, high-trust), then ship the two things Josh actually asked for (narrative + chat) on the existing static substrate, then deepen.

1. **B1 — carrying-cost fix (S).** One-line correction + rename + band; kills the live ~4x overstatement. Highest trust-per-hour. Do today.
2. **X1 — framing cleanup (S).** README dark-basemap line, surface manifest freshness/coverage, honest "sample trade data" label. Removes the §3 overstatements.
3. **P1 — durability receipt or README softening (S).** Run one real docker tick and commit the `meta_attribution` receipt, or stop claiming an always-on agent you can't show.
4. **N-Stress — Global Stress Index (M).** Pure compute over existing series; gives the at-a-glance VP number and the spine the brief/chat will cite.
5. **N-Brief — weekly narrative brief (M).** The first half of what Josh wants; deterministic, cited, reuses the stress index + diff. Hero card above the feed.
6. **C1 — Tier-1 client-side chat (L).** The capstone, but ship the $0 Pages-native version (every number traceable to a sidecar). Reuses the entity index + brief diff from steps 4–5.
7. **P2 — production self-refresh (M).** Cron `publish_static` + commit so the now-richer sidecars stay fresh; also fold in P3 (ships) and P4/P5 (dedup + staleness tests).
8. **B2 → B3 — routing + cost stack (M→L).** Real-CSV-safe routing, then the banded Cost-of-Disruption stack with "show your work." B2 is a prerequisite for U1 (the JS routing port).
9. **U1 — in-browser CSV upload (L).** Converts the demo into a tool; depends on B2's resolver math being ported to JS. Then U2 (what-if slider) is cheap.
10. **D-W2 → D-W3 → D-W4 — official corroboration, weather, dwell (L each).** The remaining data layers; official-event corroboration (W2) first since it's the receipt Josh explicitly wants.
11. **Polish tail (X2–X9):** scrubber-drives-feed, deep links, search, onboarding, mobile, watchlist/notify, email+RSS digest, export — slot in opportunistically; X7/X8 pair naturally with the brief.

_Order rationale: steps 1–3 are sub-day trust fixes; 4–6 deliver Josh's two stated wants (narrative + chat) on the existing static site with no new infra; 7 stops the freshness rot before the surface grows; 8–9 deepen the business value and flip it from demo to tool; 10 adds the corroboration/weather/dwell depth; polish trails throughout._