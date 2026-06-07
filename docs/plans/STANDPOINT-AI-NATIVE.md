# Standpoint — The AI-Native Architecture

## 1. Executive summary

Standpoint's next chapter is not "add an AI reasoner." It is to make **one substrate, one grounding gate, one multiplicity control, and one capability firewall** the single foundation that the reasoner, the signals board, bitemporal time-travel, and the `hyp_*` association tier all *query* — never a feature each bolts its own honesty onto. The AI-native thesis is inverted from the industry default: **the depth lives in offline, deterministic-where-possible reasoning that emits cited artifacts a static site serves at zero marginal cost — the LLM renders and judges, it never selects or decides.** Every claim is a type that *cannot hold an ungrounded sentence*, every "significant" means the same thing across the whole test universe, and the agent's tool layer is physically read-only — these are CI facts, not comments, and they are the exact, falsifiable opposite of centrum-ai's unfalsifiable "99.7% cascade." The portfolio thesis fits on one screen: *an AI that structurally cannot fabricate causation, with a fail-closed gate that proves it.*

**The one foundational decision everything depends on:** wire `build_substrate` into `refresh.yml` and make `fct_observation` the single, all-tier, append-only, per-run-`knowledge_time`-stamped read corpus — because every other pillar is a query over it, and a clever reasoner over a SPINE-only, single-snapshot, un-accumulated index is just centrum with better manners.

---

## 2. The foundation (build this first)

The three adversarial critiques agree on one thing the six pillars blurred: **the reasoner is the smallest, last consumer — not the keystone.** The keystone is the substrate + the shared contract. Build the store, prove it point-in-time correct and all-tier, gate it with one verify / one FDR / one firewall — *then* let the agent talk. Foundation precedes voice; that ordering *is* the honesty thesis expressed as a build plan.

### 2a. The shared substrate — `fct_observation` as the one index

Today `substrate.py:build_fct_observation()` is `CREATE OR REPLACE`, SPINE-only, single-snapshot, with a static `knowledge_time = "2026-01-01T00:00:00"` literal, and **zero pipeline callers** (only `test_substrate.py` invokes it). The contract every pillar binds to:

- **One table, four readers.** The reasoner retrieves from it; the signals board is a `GROUP BY metric_key` over it; time-travel is `WHERE knowledge_time <= :as_of` over it; `hyp_*` joins two `metric_key` slices of it. Not four bespoke indices.
- **All tiers land** (SPINE/SIGNAL/CONTEXT/DERIVED), bitemporally, append-only.
- **`dim_entity` is the join key.** SIGNAL rows crosswalk to `entity_key` where spatial (via `resolve_locode`), else a synthetic `signal:<id>` entity — so a signal can join a port at all.

### 2b. The honest-reasoning contract — `derived/contract.py` (new keystone)

Everything reusable lives here, not in `reason.py`. This is what makes the foundation *foundational* rather than a script: `hyp_*` doesn't invent honesty rules, it emits these types and inherits this gate; the signals board doesn't invent a citation format, it renders `Claim.cites`; bitemporal doesn't add a provenance scheme, `RetrievedObservation` already carries `knowledge_time`.

- **`RetrievedObservation`** — the *only* currency reasoning is allowed over: `{entity_key, metric_key, value, method, as_of, knowledge_time, tier, lineage_run_id}`. Constructed *only* by the retrieval layer, never by the model. The model never sees a table row (which collapses past ~1k tokens); it sees a typed observation it must cite by `lineage_run_id`.
- **`Claim`** — `{text, cites: list[lineage_run_id], association: AssociationObj | None}`. A claim with empty `cites` is **unconstructable**: `__post_init__` raises. *You cannot represent an ungrounded claim in memory.* The honesty thesis as a type, not a lint.
- **`AssociationObj`** — `{layer_a, layer_b, lag, method, window, confounder_note}`. Associations are emitted as **typed objects, never sentences** — because the causal-illusion literature (Northwestern, *Illusion of Causality*) shows prose and bar-charts produce the *highest* false-causation inference. Linting a struct is decidable; linting prose about two co-moving series is not.
- **The law: `ground_or_abstain(draft) -> Claim | ABSTAIN`** — wraps `store.verify()`. Re-verifies every cite against the live store at emit time; any abstain drops the whole claim. This is the *same function* chat will eventually call. One gate, four pillars.

### 2c. The retrieval/grounding interface — the store IS the index

No embeddings, no vector DB — a defensible bet, because the structured store already *is* tier-stamped and lineage-bound, eliminating the embedding-drift failure mode of text RAG entirely. `derived/retrieve.py` exposes week-scoped primitives over the existing read surface (`store.catalog()/get_layer()/nearby()`, re-exported as the MCP `list_layers/get_layer_facts/nearby/verify` tools):

- **`whats_changed(since_knowledge_time)`** — week-over-week deltas from the bitemporal index as `RetrievedObservation[]`. **This is real retrieval, not snapshot-only.** *(Critical critique fix below: it does NOT order the briefing by magnitude — see §3.)*
- **`facts_for(entity_key)`** — `get_layer()` + `nearby()` fused. **Fix required first:** `nearby()`'s hardcoded `_NEARBY_SOURCES` tuple must derive from `REGISTRY` (which already tags CONTEXT layers), so new layers auto-enroll instead of going invisible to the reasoner.
- The agent emits **typed, parameterized tool calls validated against `fct_observation`'s schema — never raw SQL strings.** DuckDB(-WASM) is the execution engine; the model decides *what* to ask, the store decides *what's true*.

**Why foundational-first (the anti-pattern named):** a fluent weekly briefing over a SPINE-only, single-`knowledge_time`, un-accumulated index is exactly centrum's sin with politeness. The substrate is the moat; the prose is the veneer. Steps 0–3 *must* precede the reasoner.

---

## 3. The reasoner architecture

This is where the three critiques are load-bearing and I resolve the central disagreement explicitly.

### The disagreement: LLM vs deterministic template — resolved

The cargo-cult critique is correct and I am adopting it: **the honesty constraints are so tight they squeeze the model's degrees of freedom to near zero, so the LLM must justify itself against a Jinja-template null hypothesis — and mostly it can't.** The pillar's three-agent planner/generator/evaluator split with per-signal-family subagents is **cut**: with ~30 weeks of data and ~22 layers, that's multi-agent theater solving a context-window problem that doesn't exist, and a reviewer who knows agents will read it as resume-driven design. The honest division of labor:

| Job | Owner | Why |
|---|---|---|
| **Selection** (which deltas appear, in what order) | **Deterministic.** Fixed key (`enrich_order`/`entity_key`), publish the *full* changed-set | A model ranking by magnitude is a latent risk score (see below) |
| **Grounding** (does the number match its cite) | **`verify()`** | Already deterministic, ground-or-abstain |
| **Association** (lead-lag stats) | **`hyp_*` math** (scipy) | Not an LLM job |
| **Phrasing** a pre-selected, pre-grounded, pre-typed `Claim[]` into readable English | **LLM, single cited call** | The *only* genuinely-LLM job, and it's small |

**The fence (cargo-cult critique):** the model may only *rewrite a deterministically-built `Claim[]` into prose*, with attribution re-checked after. **The LLM never chooses a claim, only renders one.** If a future change can't articulate what the template can't do, ship the template — it's the more honest artifact and the better portfolio story ("I proved the LLM was unnecessary in the author seat").

### The selection-function fix (honesty-erosion critique — load-bearing)

The single sharpest critique: **causation sneaks in through selection, not tokens.** A briefing of five individually-true, individually-cited facts, *ordered by magnitude and curated to the scariest five*, is centrum's move with better citations — and no gate inspects ordering. So `whats_changed` is **demoted from "the briefing's spine" to a retrieval primitive**: ordering is a fixed deterministic key, the *full* changed-set is published (not a curated top-5), and `expected_false` sits on the set. **Selection is mechanical, not the model's.**

### The generation flow (two-pass, native Citations)

The load-bearing API constraint *dictates* the shape: **Citations and Structured Outputs are mutually incompatible (400 error)**, because citations interleave citation blocks with text. So:

- **Pass 1 — cited rendering:** one Agent SDK call (gather→render→verify, *not* multi-agent) over the deterministically-assembled fact pack, store sidecars passed as `custom content` documents. Output: **native-cited text blocks** where each `char_location` is a *hard verbatim pointer* into a real `fct_observation` row — the eval re-resolves the pointer against published bytes, so the model's self-report is never trusted. Tools are **read-only only**: `assert_read_only()` (already scanning `WRITE_TOOL_MARKERS`) now points at the agent's tool registry — the capability firewall extends to the agent runtime.
- **Pass 2 — validated JSON:** transform cited blocks → `Claim[]` via `ground_or_abstain`, serialize `ai_briefing.json` carrying verbatim `cited_text` + `lineage_run_id`.

**Zero-cost:** batch API + prompt caching on the cached store documents round the weekly cost to ~zero. *(This is one sentence, not an architecture pillar — the cargo-cult critique is right that at this volume it's already free.)*

### The artifact contract

`ai_briefing.json` stays a list of `{text, cites[]}`, now **produced not hand-authored.** The existing `derived/briefing.py:validate()` (tier==DERIVED, metric is None, every cite ∈ `{d.id for d in REGISTRY}`) + `scan_rendered()` (fail-closed causal/forecast-token firewall) stay as the publish gate; §8 adds the attribution check. The one missing line of glue in `refresh.yml`: `python -m freight_radar.substrate` then `python -m freight_radar.derived.reason --write-briefing` with `validate()` as a hard publish gate. **Undeployed = not done.**

---

## 4. hyp_* — ML-within-honesty (guardrails first)

This is the tier most likely to quietly become centrum. The discipline is inverted from everything else: **build the rendering firewall before the math, and ship the math dark.** All three critiques converge here — the fence is the portfolio piece, the math is a footnote.

### The firewall FIRST (honesty-erosion critique — non-negotiable sequencing)

The pillar's "data-gating until interstitial ships" was specced as a *path convention* (`publish.py` writes `data/hyp/`, the globe "doesn't enumerate it"). **That's a comment, not a firewall.** The fix, fail-closed, **must exist in CI before `associate.py` is written:**

1. **CI structural:** extend the import-graph test so any `frontend/src/**` module that fetches a `data/hyp/` sidecar **fails the build** unless it also imports `<AssociationStamp/>`. Same fail-closed posture as `scan_rendered()`, now spatial.
2. **Tier:** add `Kind.HYP` to `registry/layers.py` (joins `{CONTEXT, SIGNAL, DERIVED}` on the non-spine side of the firewall test). New one-line CI assertion: **no module under `hyp/` may be imported by `detect/`, `publish.py`, or `substrate.build_fct_observation`** — HYP reads the substrate; the substrate never reads HYP.
3. **Descriptor honesty:** `metric=None` (routes HYP through the same no-measured-value `validate()` path as DERIVED) + a new `association_metric` field the renderer keys on + `honesty_note="ASSOCIATION_ONLY · UNVERIFIED"`.

### The math (scoped down per the founder-reality critique)

The full `associate/candidates/validate` tri-module suite with golden-mastered pre-registered candidate sets is **governance for a research program that doesn't exist yet** — cut to a single honest lead-lag function in `hyp/associate.py`:

- **Lead-lag cross-correlation on first-differences**, bounded lag window (±8 weeks), read **as-of** from `fct_observation` (no lookahead). **Spearman** (rank) as the headline — robust to z-score tails, honest about "monotone co-movement, not a fitted model."
- **Pre-whiten** (strip AR(1)) so reported `n_eff` is honest — Pearson on autocorrelated weekly series manufactures significance.
- **Cut: mutual information** (hard to calibrate, easy to over-read — pure complexity tax).
- **One pooled BH family per run**, `m` = full candidate count passed explicitly (the load-bearing `multiplicity.py` pattern). Surface `expected_false = q·n_significant` verbatim — a block that can't state its own expected-false count fails validation.

**The honest bet:** lead-lag mining on ~30 weeks of weekly data will *mostly find noise, and BH will correctly kill most of it.* That is the point — a tier allowed to find patterns and structurally constrained to admit when it hasn't is the strongest possible anti-centrum artifact.

---

## 5. Bitemporal time-travel

### The opinionated stance: snapshot the thin index and only the deltas — never the wide tables

Keeping a dated copy of every sidecar per run re-creates exactly the bloat the git-history purge killed. The bitemporal corpus lives in *one* narrow append-only place — `fct_observation`.

### Data model (three changes to `substrate.py`)

1. **Stamp `knowledge_time` per-run** from `ctx.as_of` (already threaded through `temporal/activities.py`) + `lineage_run_id`. Drop the static literal — without this there is no as-of axis; every row shares one knowledge-time and "what did we believe last week" is unanswerable.
2. **Append, don't replace.** `INSERT INTO`, persisted as a Hive-partitioned Parquet ledger `store/observations/knowledge_date=YYYY-MM-DD/*.parquet`. DuckDB-WASM reads Hive partitions natively with predicate pushdown — a week's index is kilobytes. Idempotent on `(entity_key, date_key, metric_key, knowledge_time)`, so the at-least-once self-refresh Action is safe.
3. **Revisions as new rows.** Relax the `source_observed_at == date_key` invariant in `test_substrate.py`: a PortWatch restatement lands as a new row with the *old* valid-time but a *new* `knowledge_time`. Restatement and original coexist; neither is destroyed.

### PIT query — one primitive, three surfaces

Add `store.as_of(knowledge_time, *, layer=None, entity=None)` beside `verify()`, compiling to "the latest belief we held as of K, for each (entity, date, metric)." It backs all three reads so there's no second implementation to drift: a saved DuckDB-WASM view `belief_as_of(K)`; the agent retrieval primitive (`verify(claim, as_of=K)` grounds against a *past* belief state); one MCP tool `belief_as_of(...)` inside the read-only firewall.

### The killer demo (resequenced per founder-reality critique)

- **Ship the query primitive now** (`store.as_of`) — cheap, load-bearing for honesty.
- **"Claimed-then vs measured-now"** is the demo to chase: snapshot centrum-ai's "99.7% cascade" as a single `tier=CONTEXT, method='external_claim'` row with its own `knowledge_time` = their publish date. The Board renders *their* as-of claim next to *our* measured value for the same entity/date. We never say they're wrong — we show claimed-when next to measured-when, and stop. **The honesty thesis weaponized into a single row-diff.**
- **Defer the PortWatch-restatement divergence UI** — it depends on a real revision existing in accumulated history you don't have yet. Ship the primitive; defer the polish.

**Honesty-erosion critique fix:** the staleness predicate ("present-tense claim must resolve to max-knowledge-time row") cannot live *only* in `reason.py`'s loop — the globe and Board read sidecars directly and would render a stale CONTEXT value as current. The staleness check belongs on the rendering path too, or it's asserted only where no human looks.

---

## 6. Signals + signals board

### New families (the `commodities.py` loop, scoped per founder-reality critique)

Each is the proven template: FRED public-domain allowlist → imported `parse_series()`/`zscore_12mo()` → pure `compute_signal()` → `run(ctx)` degrade-to-absent → one `LayerDescriptor(kind=SIGNAL)`. Keyless, firewall-clean (never imports `detect/`):

1. **`energy.py`** — WTI/Brent, Henry Hub gas, **US diesel** (the load-bearing one: actual operating cost of the spine — the most *defensible* signal-to-spine adjacency without crossing into causation).
2. **`slack.py`** — inventories-to-sales ratios, fed **month-over-month delta** (`transform="mom_delta"`), not raw z — because I/S ratios are regime-sticky and a 12-mo z flags the 2021 COVID whipsaw forever.
3. **`labor.py`** — truck/warehouse/rail employment, MoM-delta, disclaimer-explicit US-only proxy.
4. **CUT: `leading.py` / OECD CLI** — the pillar flagged it a bet (z-of-a-model-output risks the forecast implication the moat forbids); both founder-reality and I agree, cut entirely.

### The FDR fix (pulled FORWARD per founder-reality critique)

This is the one "refactor existing code" item worth doing *early*: today each family runs its **own isolated `control_z`** — four silos of 5–6 tests, so "significant" silently means four different things. A sharp interviewer spots it. Add `signals/pool.py`: collect every signal's z + `two_sided_p`, run **one** `control_z(zs, q=0.10, m=len(all))`, write `signals_fdr.json`; `compute_signal` emits z-only, **all significance re-stamped from the pooled gate.** The spine detector (`run_detection.py:334`, `m=n_tested`) stays its own family — ports and macro are different universes; pooling them would be dishonest.

### The board

A new view, distinct from the cited-context ring (association-only CONTEXT) and the Board comparison matrix — the **"measured · we computed this"** surface. One row per signal: name, family, latest value, **owned anomaly (our z)**, **pooled-FDR verdict** (with `expected_false` in the header so multiplicity is visible), and a **bitemporal sparkline read straight from `fct_observation` filtered to `tier='SIGNAL'`** with a knowledge-time scrubber. This is where landing SIGNAL rows in the index (§2a) earns its keep. Visual honesty: a distinct "we-computed" glyph/border vs CONTEXT, header disclaimer "z-scores we computed over cited public-domain inputs; an anomaly is not an event and not a forecast."

---

## 7. How they compose

**One substrate, three shared gates, one DAG.** Every pillar is a query over `fct_observation`, asserts through `verify()`, corrects through one pooled `control_z`, and is bounded by one import-graph firewall.

```
                    ┌─────────────── refresh.yml (weekly Action) ───────────────┐
ingest → publish → [substrate: build fct_observation, append, per-run knowledge_time]
                              │  (THE keystone — today zero callers)
        ┌─────────────────────┼──────────────────────┬────────────────────┐
        ▼                     ▼                      ▼                    ▼
  signals/pool.py       hyp/associate.py        store.as_of()      derived/reason.py
  (pooled FDR over   (lead-lag, as-of read,   (PIT bitemporal     (single cited call,
   tier=SIGNAL)       pooled BH, DARK)          query)             renders Claim[])
        │                     │                      │                    │
        └──────────┬──────────┴───────────┬──────────┴─────────┬─────────┘
                   ▼                       ▼                    ▼
         SHARED GATE: verify()    SHARED GATE: control_z   SHARED GATE: import-graph
         (ground-or-abstain)      (one m, one q)           firewall + scan_rendered()
```

**Dependencies (hard edges):** `substrate wired` → everything. `dim_entity all-tier` → `hyp_*` join key + signals board sparkline. `pooled FDR` → honest "significant" everywhere. `verify(as_of=)` → bitemporal-honest reasoner. `<AssociationStamp/>` + import-graph fence → *before* `hyp/associate.py`. The reasoner is the **last and smallest** node — the critiques are right to demote it.

---

## 8. The honesty + eval harness for AI

The reasoner emits *prose*, and prose is where causation gets smuggled in — so the harness is the load-bearing wall that lets us ship an LLM at all. **The reasoner is guilty until a gate proves it innocent, and the gate is code, not a reviewer.** One binary gate, `derived/gate.py::gate_briefing()`, run before the file is written *and* in CI over the committed artifact — a conjunction, all five or the build fails red, no warn-level, no override, **fail-closed** (a missing sidecar, unparseable judge, or tool timeout all count as failure):

```
GATE = validate           # tier==DERIVED, metric None, cites ∈ REGISTRY  [exists]
   AND scan_rendered      # zero causal/forecast tokens, non-boilerplate  [exists]
   AND attribution_pass   # every claim Entailed by its cited row, verbatim
   AND abstention_pass    # all bait prompts → zero claims
   AND provenance_clean   # no telemetry layer in any cite / derives_from
```

1. **Attribution (not correctness).** *Correctness is not faithfulness* (Wallat 2025) — a claim can be numerically right with a wrong cite. `attribution_pass()` checks the *link*: decompose → label **Entailed / Contradicted / Baseless** → any non-Entailed fails. Reuses the `check_chat.mjs` discipline (raw value verbatim in the cited sidecar) at claim granularity, re-resolving Pass-1's `char_location` pointers against published bytes. **Fence (honesty-erosion critique):** the LLM-judge entailment label is the one merely-*trusted* piece — so **if a claim's faithfulness isn't string-decidable, reject the claim; don't escalate to a judge.** Fail-closed means the judge is a last resort that usually has nothing to do, not the primary mechanism. *(This is a bet, and I'm marking it: the residual NLI label is the one surface I can't fully mechanize — mitigation is to keep prose minimal via typed objects + pin the judge model + golden masters.)*

2. **Language firewall (extend, don't rebuild).** `scan_rendered()` already fails on causal/forecast tokens. Associations get a *second, stricter* list: `method ∈ {pearson, spearman, lead_lag}`, `confounder_note` present and non-empty. Vocabulary *shrinks*, not grows.

3. **Abstention battery** — `tests/abstention/bait.jsonl`: ungroundable geopolitics ("will Hormuz close?"), forecast bait, causal bait ("did the quake cause the drop?"), phantom-entity bait. Each must produce **zero claims**. The literature is blunt models "fail to abstain… generating spurious arguments" — this is the eval most likely to catch real erosion. A **living fixture**: every escaped leak becomes a permanent test. *(High-leverage, under-specified AI use per the cargo-cult critique: use a model to **adversarially generate** new baits — the LLM belongs in the adversary seat, where it's irreplaceable.)*

4. **No-telemetry-into-DERIVED.** `provenance_clean()` asserts no cite/`derives_from` edge resolves to a telemetry/analytics layer — enforced like the SPINE-immutability firewall. The agent's tools are read-only *and* telemetry-blind: no tool returns view counts or "popular ports." We can *prove* the model never optimized for engagement because it was never shown it — the portfolio-legible inverse of centrum's 99.7%.

**Scorecard (`derived/scorecard.json`, on the Source Ledger):** reports the gate's receipts — `{n_claims, n_entailed, n_abstained_bait, causal_tokens=0, telemetry_edges=0, judge_model, run_id, knowledge_time}`. **Honesty-erosion critique fix: cut any cross-claim density/coverage scalar** (`n_significant/n_claims`) — it reads as "how sure Standpoint is this week," a confidence proxy the moment it renders near the globe.

**Resequence (honesty-erosion critique):** the abstention battery and attribution check **must exist before `reason.py` writes its first real briefing** — else the first artifact is hand-blessed and the gate is retrofitted to pass it. **Gate first, generate second.**

---

## 9. Build sequence

Each step is shippable and verified-live (real receipt, not "the step ran"). Foundational-first, but with the founder-reality 80/20 baked in: **the smallest store that makes the abstention demo real, then ship it** — don't serial-build six weeks before anything user-visible lands.

| Step | What | Unlocks | Receipt |
|---|---|---|---|
| **0** | Wire `freight_radar.substrate` into `refresh.yml` (after publish, before contracts). | A corpus that *exists*. | `fct_observation` sidecar live + queryable in the DuckDB-WASM console |
| **1** | Per-run `knowledge_time` from `ctx.as_of`; `CREATE OR REPLACE` → append Parquet ledger; relax `source_observed_at==date_key`; add `store.as_of()`. | Time-travel is a *query*; restatements become revision rows. | Restatement fixture: old `as_of` returns old value |
| **2** | Pooled FDR (`signals/pool.py`) + `signals_fdr.json`. | "Significant" means one thing across 22 signals. | Board header shows pooled `expected_false`; per-family silos gone |
| **3 ⭐** | **The abstention demo, end-to-end, live:** centrum "99.7%" as a `tier=CONTEXT,method=external_claim` row in the Board; `bait.jsonl` green in CI; `scan_rendered()` extended; public scorecard. | **The single most hireable artifact.** | Live screenshot of claimed-vs-measured row + green CI badge |
| **4** | All tiers land in `fct_observation` (SIGNAL via `dim_entity`, CONTEXT counts); signals board reads it. | The join key for `hyp_*`; the sparkline. | Board sparkline replays as-of z-series |
| **5** | `<AssociationStamp/>` + `data/hyp/` import-graph fence **(CI-blocking, before any math)**. | The dark-tier firewall. | CI fails on a deliberate un-stamped `data/hyp/` fetch |
| **6** | `hyp/associate.py` (single lead-lag fn, pooled BH, as-of read, writes `data/hyp/`). | Measured cross-layer association, dark. | `expected_false` in every block; not on the globe |
| **7** | `derived/gate.py` (attribution + abstention + provenance) **before** `reason.py`. | The fail-closed honesty gate. | Gate rejects a hand-crafted unfaithful briefing |
| **8** | `derived/reason.py` (single cited Pass-1 → validated Pass-2), wire into `refresh.yml`. | Briefing *derived*, not hand-authored. | `ai_briefing.json` numbers re-derive from sidecars on refresh |
| **9** | `energy.py` / `slack.py` / `labor.py`. | Signal breadth. | Three new SIGNAL rows, firewall-clean |
| **—** | *Fenced indefinitely:* chat unification onto `verify()`. | One grounding engine. | Defer — refactoring a working surface is motion when the clock is the job hunt |

---

## 10. Risks, kill-criteria & the 80/20

### The few foundational bets (marked honestly)

- **BET: the store-as-index, no embeddings.** Right *because* the structured store is already tier-stamped and lineage-bound. **Kill-criterion:** if retrieval ever needs fuzzy semantic match over free text, revisit — but it won't on `fct_observation`.
- **BET: the LLM-judge entailment label** (§8.1) is the one un-mechanized surface. **Kill-criterion:** if a claim isn't string-decidable, reject it — never let the judge be the primary gate.
- **BET: `hyp_*` will mostly find noise.** That's the *feature*. **Kill-criterion:** if a single block ever renders on the globe without `<AssociationStamp/>`, the firewall failed and the moat is breached — that's the one un-survivable bug on the public flagship.
- **BET: the briefing may be templateable.** Default to the template; make the LLM *prove* it's necessary in the author seat. Shipping the template is the *more* honest portfolio story.

### The single most hireable demo

**Step 3.** The abstention demo wired live + the bait battery green in CI + a public scorecard. It needs Steps 0–1 of substrate and the language firewall — *nothing else* — and it's buildable in days. The entire portfolio thesis in one screenshot + one CI badge: *"I built an AI that structurally cannot fabricate causation, and here's the failing-closed gate that proves it."* A hiring manager spends 90 seconds on the repo; that screen is the 90 seconds.

### What to explicitly NOT build yet

- The three-agent reasoner split + per-family subagents (theater over a corpus a single prompt handles).
- The `hyp/{candidates,validate}` tri-module suite + golden-mastered pre-registered candidate registry (governance for a research program that doesn't exist).
- Mutual information in `hyp_*` (complexity tax).
- The PortWatch-restatement divergence UI (no real revision in history yet — ship the primitive, defer the polish).
- OECD CLI signal (forecast-implication risk, zero upside).
- Chat unification (refactoring a working surface; fenced indefinitely).
- Batch-API/prompt-caching as a *design pillar* (it's one sentence — cost is already zero).

---

## 11. The first concrete steps (zero-cost, single-founder)

1. **Add the `refresh.yml` step** `python -m freight_radar.substrate` after `publish`, before `contracts`. One line of glue. Verify the `fct_observation` sidecar appears and the DuckDB-WASM console can `SELECT` it. *(Step 0 — the keystone, un-sexy, do it first.)*
2. **Kill the `knowledge_time` literal** in `substrate.py:build_fct_observation()` — thread `ctx.as_of` + `lineage_run_id`, switch to append Parquet, add the idempotency key. Add `store.as_of()` beside `verify()`. Relax the `test_substrate.py` invariant + add a restatement-replay test. *(Step 1.)*
3. **Write `signals/pool.py`** — collect all signal z's, one `control_z`, write `signals_fdr.json`, re-stamp `fdr_significant` from the pool. Cheap, high-credibility, fixes a real correctness bug. *(Step 2 — pulled forward.)*
4. **Build `derived/contract.py`** (the `RetrievedObservation` / `Claim` / `AssociationObj` types + `ground_or_abstain`) — so every later pillar inherits the gate instead of inventing one. No model call yet; this is pure types.
5. **Stand up `tests/abstention/bait.jsonl` + the attribution check skeleton in `derived/gate.py`** — the gate exists *before* the reasoner writes anything, so the first real briefing is gated, not hand-blessed.
6. **Ship Step 3 — the abstention demo — and stop to look at it.** That's the deliverable a staff-AI-eng interviewer remembers: a fail-closed honesty gate over a real substrate, the falsifiable opposite of "99.7%."

The through-line: **build the store, prove it point-in-time correct and all-tier, gate it with one verify / one FDR / one firewall — *then* let the agent talk.** If the foundation is right, the "AI" is almost an afterthought — and admitting that is the most senior, most honest thing this architecture can say.
