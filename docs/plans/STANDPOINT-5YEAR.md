# Standpoint — The 5-Year Plan

## 1. Executive Summary

Standpoint is a finished, deployed portfolio flagship whose entire value is that **its honesty is a build artifact, not a promise** — and the single most important truth in this plan is that *the job hunt is the exit*. The defensible asset is not a market position but a hiring artifact: a staff-level engineer made epistemic restraint a compile error, machine-enforced across a 2065-port measured spine, a typed registry, an import-graph firewall, an FDR gate, and a bitemporal store. The one bet that compounds *both* the $200K+ job hunt *and* any future product optionality, at near-zero marginal founder-cost, is **depth on the substrate: bitemporal-everywhere + the git-bloat fix + a rendering/language honesty firewall** — plumbing that makes the staff-engineer story true while keeping every "company" door open as a clean seam rather than a sunk build. Everything that requires *selling, supporting, or SLA-ing* is fenced behind falsifiable revenue gates, because the only resource that is actually scarce is one founder's hours, and the job hunt wins that contest every time. This plan optimizes for surviving Josh's *success* — the real competitor is not Kpler, it's "Josh gets a great job and the feeds quietly rot" — so the architecture's north star is a system that **rots gracefully and self-defends**, not one that scales a sales motion that doesn't exist.

---

## 2. The Honest Premise

**What this plan IS:**
- A strategic operating doc for a *deployed portfolio piece* whose tactical build (P0–P6) is genuinely done, verified, and live (`joshs444.github.io/freight-radar`, commit `121be45`, receipt-verified).
- Optimized first for **credibility and hireability** — the proven, banked value — and second for keeping product/company optionality alive as *seams*, not roadmaps.
- Explicit about its single binding constraint: **one founder's hours.** A single founder can *ship artifacts and write posts*. The moment a motion requires selling, supporting, or SLA-ing, it competes with the job hunt and loses.

**What this plan is NOT:**
- It does **not** assume a team or funding. Every line item that needs a second human is fenced behind an explicit gate and labeled "DO NOT BUILD WITHOUT A PAYING TENANT." Those sections are *designed seams*, not work items.
- It does **not** trade the honesty brand for growth, ever. The brand is the entire moat; any revenue that required relaxing the FDR q-value, adding a risk rank, or shipping a directional call is, by definition of this plan, **not revenue** — it's brand liquidation.
- It does **not** pretend white space is a market. Owning the word "verifiable" is a credibility prize; charging for it is unproven and treated as a hypothesis throughout.

**The two non-negotiables, restated as law:**
1. **Honesty is mechanical or it is nothing.** Every "we'll just say no" in this plan is a bug until it's converted into a gate that makes "yes" structurally impossible. "The founder will resist temptation" is the *absence* of a guardrail dressed as virtue.
2. **Zero-marginal-cost holds until a paying customer forces the fork — and then the fork is named, priced, and isolated, never a silent erosion.**

---

## 3. The Three Horizons

Each horizon ships standalone value *even if the next never funds*. The discipline is constant: **scale the invariant, not the layer count; declare latency per-layer; quarantine ML in data AND pixels; name every place zero-cost has to die before letting it.**

### Year 1 — Make the substrate self-defending and the story unimpeachable

| Goal | Concrete bet | Success metric | Kill metric |
|---|---|---|---|
| **Survive Josh's success** (the real threat) | Move sidecars off the bloating `.git` (49 MB clock) to GitHub Releases as a blob store (LFS breaks zero-cost; Releases don't). Matrix-shard the weekly Action. Auto-demote stale feeds to CONTEXT/dark without human intervention. | `.git` growth flat; a feed that breaks schema self-demotes with zero manual touch; refresh survives 8 weeks untended | If untended refresh rots within 8 weeks, the metabolism failed — cut layers until it doesn't |
| **Bitemporal everywhere** (the appreciating moat) | Generalize the per-row knowledge-time stamp from `fct_observation` to *every* layer. "What did the store believe on date X" becomes a free query. | Every observation carries valid-time + knowledge-time + lineage; PIT replay works on any layer | — (pure plumbing; near-zero buyer risk) |
| **Close the one honest gap** | `SPINE == 1` as a CI predicate: exactly one *measured root* Producer; the 11 render-layers are children via an explicit `derives_from` edge. | CI fails if a second SPINE root or a self-promoted tier appears | — |
| **The rendering/language firewall** (the critics' #1 finding) | Run the causal/forecast lexicon against *rendered* `ai_briefing.json` every build — **fail the build on any causal/forecast token > 0**. The DERIVED `metric=null` schema becomes CI-rejected-if-violated, forever. | A briefing that drifts "co-located with" → "amid escalating" fails CI | — (ship now, not in H2) |
| **The hireable demos** | (a) `verify(claim)` as a *demo*, not a service: a screen-recording of an agent suppressing an ungrounded geopolitics claim because the store returned "no measured observation supports this." (b) The honesty harness published MIT-OSS with one blog post. | One screen-recording + one OSS repo + "I made honesty a compile error" post live | — |

### Years 2–3 — Deepen the honest-RAG and prove (or kill) external pull

| Goal | Concrete bet | Success metric | Kill metric |
|---|---|---|---|
| **Honest retrieval over the lineage graph** | BM25/embeddings over method-stamped facts (not free text). Every reasoner claim resolves to `(entity, layer, valid_time, method)`. The store's lineage-completeness means the agent *cannot* cite something uncited. | A grounded-chat answer where every sentence resolves to a stored observation | If retrieval can't beat the current format-only chat on groundedness, it's polish — stop |
| **ML through the front door, fenced in pixels** | `hyp_*` quarantined tier: a model proposes "A and B co-move" → enters stamped `UNVERIFIED` → routed through the *same* FDR/changepoint gate as the spine → surfaces only as association + method + error rate, never forecast. **Held to SQL console / agent surface ONLY — never the globe — until a rendering firewall guarantees `hyp_*` never renders co-located with a SPINE anomaly without an interstitial honesty stamp.** | `hyp_*` lives in data + agent surface; firewall blocks code-path AND visual co-location | If the rendering firewall can't be built, `hyp_*` never reaches the globe. Period. |
| **The falsifiable external-pull test** | Does *one* external team build on the MCP surface and notice if it's gone? | ≥1 external project depends on the read-surface | No external dependency after 24 months → the substrate is a single-player tool; treat accordingly |
| **Bitemporal track record accrues** | Weekly refresh deepens a never-restated corpus no API vendor keeps. Optionally snapshot one competitor's public forecast weekly to enable "claimed-then vs measured-now." | A multi-year PIT corpus exists and is replayable | — (appreciates passively) |

### Years 4–5 — The company option, kept warm as a seam

> **DO NOT BUILD WITHOUT A PAYING TENANT.** This entire horizon is a *designed seam*, not a roadmap. It is described once, fenced hard, and not iterated on.

| Goal | Concrete bet | Gate to even start |
|---|---|---|
| **Substrate-as-infrastructure** | The read-surface (`catalog/get_layer/nearby` + MCP) becomes a tenant-scoped API over the *same* bitemporal store; multi-tenant isolation **is the honesty firewall reused** (a tenant can read lineage, never mutate the spine). | A paying tenant exists. Not an LOI — an invoice. |
| **The deliberate exit from static topology** | Per-tenant query over full DuckDB history (not snapshots), live MCP endpoint, auth — all require a backend (MotherDuck or thin Postgres + object store). This is where zero-cost *intentionally* dies, priced and isolated. | Single-founder breaks here; needs a team. Only at this gate. |

---

## 4. Product & Company — The Decision Tree

The obvious beachhead — the supply-chain risk buyer — is **rejected**. That buyer pays for alerts and decisions, exactly what the thesis forbids; you'd lose to Everstream or break the brand. Selling restraint to a CSCO is selling a diet to someone who came in for dessert.

```
Gate 0 — PORTFOLIO PIECE ............................ DONE. Already paid for itself.
  Value: $200K+ as EVIDENCE Josh can build this, today, with zero customers.
  Pricing it as a product LOWERS this value (now it must survive a market that
  pays for restraint — which nobody does) while banking nothing.
        │
        ▼
Gate 1 — SIDE PROJECT (0–6 mo) ...... THE ONLY GATE COMMITTED PRE-JOB
  GO:    ≥3 strangers use the MCP store / SQL console unprompted, OR one
         quant/researcher asks "can I get this as a feed?"
  NO-GO: crickets after launch posts → stays a self-tended demo (fine outcome)
  Cost:  ~a weekend/month of feed-tending
        │
        ▼
Gate 2 — REAL PRODUCT (12–24 mo) ...... revenue test WITH an honesty clause
  GO:    3 paying design partners at $500–2k/mo — real invoices, not LOIs —
         for the PIT feed OR the agent store
  ▸ HONESTY-PRESERVATION CLAUSE (load-bearing): revenue that required relaxing
    FDR q, adding a risk rank, or shipping a directional call DOES NOT COUNT.
    The gate measures "did the brand survive payment," not "did someone pay."
  NO-GO (the stated-honest likely outcome): applause, citations, tweets, no AR.
         People love the demo and nobody pays for restraint → stays a side
         project. That is a SUCCESS, not a failure.
        │
        ▼
Gate 3 — FUNDABLE COMPANY (conditional branch, NOT the plan)
  GO:    design-partner revenue grows without Josh hand-selling; the
         agent-store shows pull from MULTIPLE AI-platform teams (it's infra,
         not a viz)
  Only here does single-founder break and zero-marginal-cost intentionally die.
```

**What would have to be TRUE for this to be a company, not a portfolio piece:**
1. Someone pays for point-in-time-correct cited signal — the buyer is a quant/data desk, not a risk officer.
2. The agent-store gets *external pull* — ≥1 team builds on the MCP surface and would miss it.
3. The PIT track record is *allowed to accumulate* for 3+ years without Josh abandoning it — which collides directly with the job hunt.

**The honest call:** pursue Gate 1, hold the line at Gate 2's *honesty-clamped* revenue test, treat Gate 3 as real-but-conditional. **The most likely failure mode isn't competition — it's Josh getting a great job and the feeds rotting.** Build for the world where the job hunt works, because that's the likely one.

---

## 5. Platform North-Star

**The core claim:** everything already reduces to the typed registry + `fct_observation`, and honesty is a *compile-time fact*. That is the asset that scales. The mistake the obvious plan makes is "more layers + more real-time." Wrong. **Scale the invariant, not the layer count.**

**Do NOT chase real-time across the board.** Real-time is where zero-cost dies and forecast-temptation peaks. Instead: a **tiered freshness contract** as a typed, firewall-checked registry field — `cadence: {batch_weekly | batch_daily | poll_hourly | stream}`. Latency becomes a *declared per-layer property*, not an architecture rewrite. Most layers stay weekly forever, and that's correct.

**Sequenced evolution:**

1. **H1 — self-defending substrate.** Bitemporal-everywhere → free "what did we believe on date X" query. Lazy/tiled fetch via a `manifest.json` (the highest-leverage unbuilt plumbing) so 100+ layers survives a static site by fetching only tiles in view. Git-bloat fix + matrix-shard. `SPINE == 1` enforced. *Staff-level story: I made a 100-layer open-data platform maintainable by one person by making correctness mechanical.*
2. **H2 — honest-RAG + ML-within-honesty.** Retrieval over method-stamped facts. The `hyp_*` quarantine: ML enters through the front door the brand left open (method + error rate) while the firewall keeps the back door (causation/forecast) physically shut. **The subtlest and most dangerous move in the plan** — and the critics are right that the firewall enforces *code-path direction*, not *visual/semantic non-implication*. So the guardrail is mandatory: **a rendering firewall before `hyp_*` ever touches a pixel.** Until then, agent/SQL surface only.
3. **H3 — multi-tenant substrate (fenced).** The multi-tenancy isolation *is* the honesty firewall reused. Built only against a paying tenant.

**Honest cost concession:** retrieval-augmented reasoning at *query time* is where zero-cost can break (embedding + inference). The weekly offline artifact stays free; a live agent API, if it ever appears, is the **first deliberate paid tier** — priced and isolated, not a silent erosion.

---

## 6. Positioning & Category

**The wrong shelf:** "supply-chain risk" / "geospatial intelligence." There Standpoint is a feature-poor entrant against Kpler's ~$5B war chest and Palantir's lineage-as-table-stakes.

**The category to name and own** (currently empty): **the verifiable world-model** — the layer underneath everyone else's claims that proves them. Not "we predict the world." **"We let you check anyone who does."**

**The five-year arc — a positioning escalation, not a layer count:**
> **portfolio piece → reference implementation → cited standard.**
> Year 1 *demonstrates* (Josh built the honest thing alone). Years 2–3 *reference* (others build against it). Years 4–5 *standardize* (the honesty predicates are what people cite when they ask "is this source trustworthy?").

**Manifesto one-liners (load-bearing convictions):**
- **Honesty you can compile.** A disclaimer is marketing; an import-graph firewall that *fails CI* when context touches the measured spine is a fact.
- **Restraint is a feature, not a gap.** The market is drowning in confidence and starved for *checkability*.
- **We tell you what we don't know.** The drift badge, the FDR "expected ≤k noise" line, the white-noise predicate — uncertainty as a first-class display.
- **Worth more to a machine than a CSV** — because every cell traces to its observation, an agent can *trust* it without re-deriving it.
- **On the box:** *Everyone else tells you what's going to happen. We show you what's happening — and let you check every word.*

**Where I disagree with two "obvious" positioning moves — resolving the critique explicitly:**

- **"Become the Bloomberg of honest world-state, sell the feed."** Half-right and quietly dangerous — it re-enters a data-volume race lost to Kpler on coverage and Palantir on enterprise muscle. The defensible artifact is the *verifier*, not the feed.
- **"Be the referee / run an overclaim leaderboard."** **CUT.** Two critiques converge here and they win the argument: *being "the referee" is structurally identical to being centrum.* Both arrogate the authority to issue a confident, reductive judgment. A composite score pointed at named genres ("the 99.7% crowd") *is* the centrum move in reverse. The anti-centrum stance is to **refuse the judgment seat entirely** — only ever say "here is the observation, the method, the date, and here is what we cannot speak to." Keep at most a *self-applied* honesty scorecard (Standpoint grading Standpoint, already shipped). And during a job hunt, a GitHub-Pages site picking public methodology fights is a credibility *liability* — the one fight where their distribution beats your correctness.

**Keep the anti-centrum framing sharp, not timid** — the foil is the distribution engine, and Standpoint is *long volatility on AI hype*: the more the field overclaims, the more valuable the one thing that doesn't. But the sharpness lives in *contrast of method*, never in *grading them*.

---

## 7. Moat & Competition

**The candidates, honestly ranked by durability against a funded incumbent — corrected by the adversarial read:**

| # | Candidate | Durability | Verdict (post-critique) |
|---|---|---|---|
| 1 | **Bitemporal track record** — years of never-restated, PIT-honest data | **Highest** | The *appreciating* moat. No satellite can backfill time. The plan originally ranked this too low. |
| 2 | **Honesty-as-compile-fact** (firewall, FDR, drift contracts, golden masters) | **Medium** | The trust *accelerant* and the résumé proof — but copyable in a quarter, so NOT the durable moat. |
| 3 | **Bitemporal read-surface / agent substrate** (`fct_observation` + MCP) | **Medium** | The real *product* if any product exists — gated on external pull. |
| 4 | **Brand / epistemic position** | **Medium-narrative** | Durable as narrative, undefendable as business. Downstream of #2. |
| 5 | **Open-data curation** (32 feeds) | **Low — a liability** | More layers = weaker moat. Fewer, deeper, self-demoting layers. |
| 6 | **The spine itself** (2065-port FDR) | **Low** | Table stakes; Kpler does it better with better data. |

**Resolving the deepest disagreement — is enforcement a durable moat?** The COMPETITIVE take said "you built it in, they'd tear theirs out." The third adversarial critique demolishes this with a concrete counter-move that the plan *must* concede: **Kpler doesn't retrofit — they spin up "Kpler Verified," a greenfield, read-only, cited, association-only satellite built in a quarter by four engineers, fed by their proprietary AIS.** Now they have the firewall *plus* sub-daily vessel truth Standpoint can never touch. The "expensive-to-retrofit" asymmetry is a false dichotomy: there's a cheap third door. And the harness being "weeks to package" cuts *against* you — if it's that portable, they package their own in weeks.

**So the corrected moat thesis:** the firewall is the **day-one trust accelerant and the hiring proof**, not the year-five defense. The year-five defense is **time**: the appreciating bitemporal corpus (#1) and — most durably — **the banked, certain recruiting value**, which no satellite competes with at all.

**Where open-data structurally LOSES, conceded without grief:**
- **Proprietary feeds / real-time** — never yours on a zero-cost Action. Concede the entire real-time quadrant.
- **Enterprise sales + capital** — Interos raised $204M; Altana $322M to reach ~$37.5M ARR. The control-tower buyer pays for *automation* ("visibility without action is overhead") — which the thesis forbids. Respect the wall.
- **The quant-buyer fantasy** — the critique is right and it's load-bearing: **no quant puts an un-indemnified, coverage-gapped hobby feed in a money-moving model.** PIT correctness is *necessary and nowhere near sufficient*. Concede that the open-data ceiling means **there is likely no paying data customer** — and that's fine, because the customer is an *employer*.

---

## 8. Monetization (only what survived the critique)

The eliminating principle: **the only revenue that doesn't betray the roots is selling the enforcement of restraint, not the restraint itself.** Sell the forecast and you become centrum-ai with better citations. After the three critiques, most of the original menu is cut or fenced.

| Path | Status | Who pays / why | Single-founder GTM | Verdict |
|---|---|---|---|---|
| **Honesty harness as productized compliance SaaS** | **CUT the product; KEEP the OSS repo** | EU-AI-Act ML-governance teams | — | A compliance-SaaS company with quarter-long sales cycles and a security-review burden a solo dev can't carry. "Packaging is weeks" is the fantasy tell — *trust, support, security review, a buyer who'll sign* are years. **Keep:** MIT-OSS + one blog post = a banked portfolio asset. The repo yes; the company no. If ever pursued, it's a **spin-out** where Standpoint is the reference, not Standpoint's GTM. |
| **MCP-as-a-service, SLA tiers** | **CUT the paid tier** | AI-platform teams | — | SLA'd sub-weekly freshness = running a backend on-call for revenue that doesn't exist. Keep the **free MCP server** — it's the demo. |
| **Agent substrate / "cite-target"** | **FENCE behind one test** | quant desks, AI-platform teams, researchers | list on MCP registries | Named "the real business" in three docs *and* "founder fantasy / credibility-not-budget market" in the same docs. Can't have it both ways. **Test:** does one external team build on it and miss it if gone? Until yes, it's a hypothesis, not a north star. |
| **Embeddable honest-globe** | **CUT / FENCE-hard** | newsrooms, NGOs | content-led | "Won't pay rent" by the plan's own admission, and every third-party uncited layer makes the brand co-sign a fabrication. **If ever shipped:** the embed must *technically refuse to render* any layer lacking an observation→method→date chain (G0 enforced client-side). No provenance, no pixels — a contract clause is catastrophically insufficient. |
| **Design-partner consulting** | **FENCE: inbound-only** | commodity/macro desks | never go find them | A 30-hr/week sales-and-delivery motion that competes head-on with the job hunt. It's a *job substitute*, not a complement. Only if a desk *inbounds*. And the consulting trap is real: a desk *will* ask for the forecast — saying no costs revenue, saying yes costs the brand, so the Gate 2 honesty clause governs it. |

**The honest bottom line on money:** the proven, certain revenue is **the $200K+ offer the harness earns as a hiring artifact** — banked the day an offer lands. Everything else is a flagged bet on a credibility market converting to a budget market, which is unproven.

---

## 9. Honesty-at-Scale Governance

The failure mode is not a bad actor. It's **gradient descent toward engagement** — a hundred individually-reasonable concessions that sum to a forecast engine in a provenance costume. Today's enforcement covers the *code path*. The governance job is to make the *organization* — and crucially the *rendered/semantic surface* — as un-bribable as the import graph already is.

**The critics' sharpest correction, adopted as the governing principle:** *erosion in year 5 won't be a SPINE mutation that lights up CI red. It'll be a `hyp_*` dot next to a freight anomaly, or a briefing that says "amid escalating," and no test will fire because the schema is pristine.* **The next firewall must be a rendering/language firewall.**

**The gates:**
1. **`SPINE == 1` invariant** (ship Year 1). Without it, scale erodes the brand through *tier inflation* — "SPINE" becomes the prestige tier every feed wants promoted into. The categories themselves must be CI-enforced, not just the edges between them.
2. **Promotion pipeline G0–G5, adversarial by construction.** G0 provenance-or-reject (the one rule that makes Standpoint structurally incapable of becoming centrum). **Asymmetry is the whole design:** demotion is automatic and unguarded; promotion across a tier boundary is hard, gated, and requires a second sign-off. **The author of a layer cannot certify it clean** — a 24-hour cooling rule + written G-gate record solo; a separate "registrar" role (comp *never* tied to layer count or engagement) if a team appears.
3. **The DERIVED language firewall** (ship NOW, not H2). The lexicon runs against rendered `ai_briefing.json` every build; **causal/forecast tokens > 0 fails the build.** `metric=null` is inviolable schema.
4. **The mirror rule for the human loop:** *no behavioral telemetry ever flows into DERIVED generation.* The firewall blocks DERIVED→numbers; this blocks engagement→DERIVED. Written as a lineage test the instant any telemetry exists. **The single most important governance rule in the plan** — the moment "which briefing got clicked" feeds what the briefing says, Standpoint is an engagement-optimized forecast machine.
5. **`verify()` can only ever return a lineage lookup** — never a confidence, never a boolean verdict on an arbitrary claim, never "true/false." If it can't classify a claim as in-scope, it returns **abstain, loudly.** The honest "no" is the product; an adjudicating boolean is centrum.
6. **Retirement is a feature; the cap is the policy.** One founder sustains ~N feeds; layer N+1 requires retiring one or raising drift-detector automation. The drift detector is **the org's metabolism**, not a monitor. A rotting feed silently demoted to dark is honest; a rotting feed left in SPINE is the lie.
7. **FDR as a published contract** when anyone pays — q-value and tested-N surfaced ("expected ≤k noise"). Resisting "just loosen q to surface more alerts" is the FDR equivalent of tier inflation.

**The kill-switch:** one dated **Honesty Charter** (~5 bright lines, each mapped to a CI gate). **If any gate is ever disabled to ship a feature, the live site auto-stamps a visible "honesty gate bypassed on <date>" banner until restored.** Degradation is *loud*, never silent. The brand doesn't die from one big lie — it dies from the first quiet bypass nobody had to announce. Make silence structurally impossible.

---

## 10. Risks, Kill-Criteria & the 80/20

**The 80/20 — the few bets that compound BOTH the job hunt AND product optionality, at near-zero marginal founder-cost (do ONLY these):**
1. **Bitemporal-everywhere + git-bloat fix + graceful-rot metabolism.** The thing that *actually fails first*; makes the staff-engineer story true; zero buyers required. Pure portfolio gold AND product foundation.
2. **The `verify()` "honest no" *demo*** (screen-recording of an agent suppressing an ungrounded claim) — the most hireable single artifact in the plan. The demo, not the endpoint.
3. **`SPINE == 1` CI predicate + the DERIVED language firewall** — hours of work, closes the one honest gap, and a perfect interview anecdote.
4. **Harness as MIT-OSS + one blog post** ("I made honesty a compile error") — a backlink and recruiter magnet at near-zero cost.

**Explicitly DO NOT do:**
- The outward overclaim leaderboard / referee position (brand-corrosive *and* a job-hunt liability).
- Any SLA'd / paid MCP tier or productized compliance SaaS (a second human's job).
- Go-find design partners or hand-sell anything (inbound-only; it's a job substitute).
- Build any H3 multi-tenant plumbing speculatively (DO NOT BUILD WITHOUT A PAYING TENANT).
- Add layers for breadth's sake. More layers = weaker moat + higher rot risk.

**Kill-criteria, named:**
- *Untended refresh rots within 8 weeks* → metabolism failed; cut layers until it survives.
- *No external dependency on the MCP surface after 24 months* → it's a single-player tool; stop pricing it as infra.
- *Month-18 Gate 2: all applause, no honesty-clean AR* → stays a side project (a fine outcome, not a failure).
- *Any revenue requires relaxing FDR / adding a rank / a directional call* → refuse it; it's brand liquidation, not income.

**The real failure mode (the only competitor that wins):** Josh gets a great job and the feeds quietly rot. The entire plan is optimized around *surviving that success* — which is why graceful-rot, self-demotion, and a fixed capacity cap outrank every move against billion-dollar incumbents.

---

## 11. The First 90 Days

Concrete, single-founder, mostly-zero-cost, all moving Horizon 1. Ordered by leverage.

**Weeks 1–3 — Stop the clock that's actually ticking.**
- Move the ~32 sidecars off `.git` to GitHub Releases as a blob store; verify `.git` growth goes flat. (Solves the 49 MB clock — *the thing that fails first*.)
- Matrix-shard the weekly Action so one schema change can't take down the whole refresh.
- Ship auto-demotion: a feed that fails its drift contract self-demotes to CONTEXT/dark with zero manual touch. **Receipt:** break one feed's schema on purpose; confirm it demotes untended.

**Weeks 3–6 — Close the honest gaps in code.**
- `SPINE == 1` CI predicate (one measured-root Producer; `derives_from` edges for the 11 render-children).
- DERIVED language firewall: lexicon scan on rendered `ai_briefing.json`, build fails on any causal/forecast token. **Receipt:** inject "amid escalating" into a test briefing; confirm CI goes red.
- Begin generalizing the per-row knowledge-time stamp to all layers (the bitemporal-everywhere work; can run in background across the quarter).

**Weeks 6–10 — Build the two hireable artifacts.**
- `verify(claim)` as a *local demo*: wire one research/coding agent to call it before asserting any port/quake/disruption fact across ~50 prompts; record the run where it returns "no measured observation supports this" and the agent suppresses the claim. **Deliverable:** a 60–90s screen-recording. Hard rule: it returns lineage-lookup-or-abstain only — never a verdict.
- Extract the firewall + FDR gate + drift contracts into a clean MIT-OSS repo with a 30-line adapter and a "this caught a real layering bug in CI" post (you have the P3 SIGNAL-imports-detector receipt).

**Weeks 10–13 — Convert artifacts into job-hunt distribution + run the Gate 1 test.**
- Publish the harness post and the `verify()` video; point résumé/outreach at them alongside the existing flagship.
- Passively watch the Gate 1 signal: do ≥3 strangers touch the MCP store / SQL console unprompted, or does one quant/researcher ask for a feed? **No active selling** — this is a read on pull, not a campaign.
- Confirm the metabolism: let the refresh run untended for the back half of the quarter and verify it survives. That receipt — *a 100-layer-capable platform that maintains itself* — is the staff-eng story, proven, not asserted.

**The 90-day through-line:** none of this needs a second human, a dollar of metered API, or a customer. It hardens the substrate, closes every honest gap, and produces two artifacts that move the *certain* win — the job — while keeping every product door open as a clean seam. That is the whole bet: **build for the world where the job hunt works, because that's the likely one, and make Standpoint the most defensible hiring artifact in the market on the way there.**
