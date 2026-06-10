# STANDPOINT — Frontend UX Overhaul Plan

> **Status: ✅ EXECUTED (P0 + P1 core) 2026-06-08 — shipped + deployed the same day.**
> Commits: `5718cf0` (P0-1 brief-as-hero · P0-2 relevance gate, `lib/relevance.ts` · P0-3
> globe markers sized by relevance) · `7ba6375` (P1-2 so-what rows · P1-4 brief-first
> onboarding + honest nav labels). **Still open:** P1-1 (top-movers digest), P1-3 (story
> grouping — see PROVENANCE-AND-CONNECTION P2-C's caution before building), P1-5
> (small-base headline rewrite; the exporter half landed separately in `70ad74e`), and P2 —
> the P2 chrome/disclaimer dedup is now tracked in [HARDENING-PLAN.md](HARDENING-PLAN.md)
> Wave 3 (H3-D). **Supersession note:** P0-1 deliberately reverses MONITOR-UX-PLAN Phase 1
> item 1 (brief default-collapsed → default-open); the code follows this plan.
> All claims below were re-verified against the live source and `public/data/flags.json` on 2026-06-07.

---

## 1. DIAGNOSIS

STANDPOINT has a strong, fully-cited asset — a computed weekly brief and a measured freight spine — and then buries it under noise and chrome. Three failures map directly onto the user's words.

### Problem A — "Where is the brief?" (the brief is real, but hidden, fragmented, and passive)

The brief genuinely exists and is good: `brief.json`'s headline is *"Ocean-freight stress is HIGH and rising — 41.6/100; Strait of Hormuz is the lead driver."* The problem is it is split across **four disconnected surfaces, none of which is the obvious answer**:

1. The `.fr-lede` headline strip — `App.tsx:340-346` — confirmed a passive `<div role="status">`, **not a button**. Shows the headline but leads nowhere.
2. `BriefCard` (the real 6-bullet narrative) — **defaults COLLAPSED**. Confirmed at `BriefCard.tsx:28-34`: `useState(() => localStorage.getItem('fr_brief_open') === '1')` falls back to `false`. The code comment (lines 25-27) admits this is intentional "so the brief doesn't steal the feed's height." It then renders as the **first child of the `.fr-rows` scroll region** (`DataFeed.tsx:563-569`), above `HazardsPanel`/`Upload`/`Exposure`/171 rows, so it scrolls away.
3. `ai_briefing.json` — a second, distinct "derived · AI" brief — renders **only** in `SourceLedger.tsx:210-287`, reachable only via the opaque **"Ledger §"** tab (`ViewToggle.tsx:14`).
4. The `StressDetail` modal's "what's moving" summary.

So a visitor told "find the brief" has two artifacts in two views, the friendly one collapsed-and-buried, the AI one behind a label no stranger can decode. The headline is shown three ways with **no click-path between them**.

### Problem B — "150+ alerts, some meaningless (+50% vs norm) — how does that help anyone?" (97% noise)

Verified against `flags.json` (171 flags):

- **Every flag is "critical."** `useMonitorModel.ts:144` hard-codes `critical: true` for every port flag and `:128` for every flagged chokepoint. In the data itself, `critical:true` appears on **0/171** flags. So `criticalCount` (`:186-189`) == total, and the feed header "*N critical · 171 shown*" (`DataFeed.tsx:531-533`) is meaningless, as is the "Critical" filter (`DataFeed.tsx`).
- **The alert set is a small-denominator artifact field.** **144/171 (84%)** have baseline < 5 vessels/day; **119 (70%)** < 2/day; **80 (47%)** < 1/day; only **12** are ≥ 10/day. **51 flags are exactly −100%** (a near-empty port going to zero); **28 are > +300%** (≈1 extra vessel on a 0.04–0.75/day base — e.g. Escobar LNG "+2000%"). **21 flags are under 50% change** — the exact "+50% vs norm" class the user named (Mokpo +12.9%, Nassau −12.5%).
- **Severity ranks deviation, not importance.** It's a z-score, so a 13% wiggle at Mokpo (sev 29) outranks a 21% drop at Los Angeles–Long Beach (sev 23), and Rugao (0.75 vessels/day) outranks LA-LB. `byCritThenSeverity` (`useMonitorModel.ts:55-58`) sorts by exactly this — its own comment says "not by noisy %," but severity *is* the noise.
- **Corroboration is advertised everywhere, populated nowhere.** `DataFeed` renders `OfficialEvent`/`StormChip`/`NewsBlock`/`MarketBlock` ("Official corroboration," "Possibly related coverage"), but **0/171** flags have `live_storm`, `official_event`, or `news`, and only **5/171** touch trade (`lane_count>0`). 97% are bare stat blips.
- **Net (verified):** under a defensible gate — *chokepoint OR baseline ≥ 10/day, AND |pct| ≥ 50% or |z| ≥ 6* — **exactly 5 of 171 flags pass**: Hormuz (sev 83), Shanghai (sev 36), Huanghua (35), Kerch Strait (29), Magellan Strait (20). There is a **cliff from sev 83 to sev 36**. ~97% is noise.

### Problem C — "Super overcomplicated" (≈16 simultaneous surfaces, dual nav, redundant restatements)

The default `globe` view (`App.tsx:300-606`) mounts ~16 surfaces at once: topbar brand + tagline + provenance line, `StressGauge`, `StormIndicator`, as-of stamp, `WorldRibbon`, `.fr-lede`, `ViewToggle`, a redundant `⌘K` chip (`App.tsx:357-365`), the `CommandPalette`, the Globe, a "History play 2019→now" button, `LayerPanel` (15 layers, 7 off by default), a GFS wind scrubber, a `TimeScrubber`, `Onboarding`, the whole `DataFeed`, and a floating `Chat`. A first-timer hits ~6 chrome strips before touching data.

On top of that:
- **Dual navigation that disagrees on labels.** `ViewToggle` says Globe/Board/Data/Ledger; `CommandPalette.tsx:26-31` calls the same views Globe/Board/**Data feed**/**Source ledger**. Plus URL hash + the redundant `⌘K` chip = three discovery mechanisms for one action set.
- **The stress index is rendered up to 4×** (StressGauge, StressDetail, Board's `fr-board-stress` strip at `Board.tsx:168-189`, and the brief headline).
- **The "possibly-related, not a cause" disclaimer is repeated verbatim in 6+ components** (LayerPanel, SignalsRail ×2, NearbyPanel, Board, Onboarding, topbar provenance).
- **An expanded flag row stacks up to 12 sub-blocks** (`DataFeed.tsx:403-444`), showing trend **three ways** (inline `fr-trend`, the sparkline, and the `fr-trendline` sentence). Most of these blocks are empty for ~166/171 flags.

### Root cause (one sentence)

The product's hierarchy is **inverted**: the cheapest-to-emit data (171 raw stat anomalies) is the loudest, most prominent surface, while the most valuable, hand-computed asset (the brief) is the quietest — and the chrome explaining the philosophy outweighs the chrome delivering the answer.

---

## 2. NORTH STAR

> **Signal over noise. The core answer in 5 seconds, zero clicks.**
>
> A first-time visitor lands and immediately reads **one expanded brief** ("Stress is HIGH 41.6/100 — Strait of Hormuz is the driver, −92%") plus the **~5–15 disruptions that actually matter**, on a globe where **marker size = importance**. Everything else — all 171 flags, every layer, the SQL console, the power nav — is one deliberate click away, never in the way. **Cut clutter, not the measured freight spine.**

Invert the hierarchy: brief = immovable hero; flags = hard-gated to signal; chrome = progressive disclosure.

---

## 3. ROADMAP

Effort: **S** ≈ <½ day, **M** ≈ 1–2 days, **L** ≈ multi-day. Reconciled across all four proposals; tradeoffs noted.

### P0 — Quick, high-impact wins (do these first; they directly answer all three complaints)

---

**P0-1 · Make the brief the always-expanded hero, pinned above the feed, with the lede wired to it**
*Answers: "where is the brief?"*

- **What:** (a) Flip `BriefCard` to default **OPEN** on first visit — `BriefCard.tsx:28-34`; respect a stored `'0'` only if the user explicitly collapsed it. (b) **Lift it out of the `.fr-rows` scroll region** (`DataFeed.tsx:562-569`) into a pinned, non-scrolling hero band directly under `.fr-lede` in `App.tsx` (~line 346), so it never scrolls behind the 171 rows / HazardsPanel / Upload / Exposure. (c) Make the `.fr-lede` strip (`App.tsx:340-346`, currently a passive `<div role="status">`) an actual **button** that scrolls to / focuses the hero brief — fold the headline into the hero so headline + bullets are one object. (d) From the hero, add a **"full AI brief →"** link that deep-links into `SourceLedger`'s `ai_briefing` block, connecting the two orphaned briefs.
- **Why:** This is the verbatim #1 complaint, and the fix is structural, not new content. The brief is strong; it's just hidden, collapsed, and fragmented.
- **Files:** `BriefCard.tsx`, `DataFeed.tsx`, `App.tsx`, `SourceLedger.tsx`
- **Effort:** **M** (the pin/move is the real work; the default-open flip is S)
- **Tradeoff:** The original comment worried a tall brief steals the feed's height. Resolved by P0-2 — once the feed defaults to ~5–15 flags, there is plenty of height to share; the old tradeoff was only painful *because* of the 171-row dump.

---

**P0-2 · Gate the flag set to signal — default the feed + globe to ~5–15 flags, keep all 171 behind "show all"**
*Answers: "150+ meaningless alerts."*

- **What:** Add **one derived predicate** in `useMonitorModel.ts` (where every row flows through — `:133-150` for `portFlags`, `:174-184` for `rows`). Reconciling the two proposed formulations into one:
  - Compute a **`relevance` score 0–1** = `importance × magnitude × corroboration`, *and* a boolean `isSignal` from a hard floor.
  - **importance:** chokepoint → 1.0; port → `min(baseline / 15, 1)`. **Critical data catch (verified):** for `kind === 'chokepoint_vessel_size_shift'` the `baseline` field is vessel **DWT/tonnage** (Magellan baseline = 32184.61), NOT vessels/day — special-case by `kind`; never normalize tonnage as a vessel count.
  - **magnitude:** `min(max(|pct_change|/100, |zscore|/8), 1)`. The field is **`zscore`** (not `z`).
  - **corroboration:** 1.0 if `business.lane_count>0` OR `live_storm` OR `official_event` OR `news`; else 0.4.
  - **Default surfaces** to `relevance ≥ ~0.2` (≈ the same as the hard gate: chokepoint OR baseline ≥ 10/day AND |pct|≥50 or |z|≥6). **Verified yields: exactly 5 flags** (Hormuz, Shanghai, Huanghua, Kerch, Magellan). A looser `≥0.15` gives ~17 — recommended starting point so the feed isn't *too* sparse; tune live.
  - **Sort by `relevance`**, replacing `byCritThenSeverity` (`:55-58`).
  - **Stop labeling everything critical** (`:128`, `:144`). Tier flags PRIMARY/SECONDARY by the gate; fix the feed header (`DataFeed.tsx:531-533`) and the "Critical" filter (which currently does nothing).
  - **Keep all 171 reachable** via an explicit "show all / +N minor anomalies" toggle in `DataFeed` and untouched in the Data SQL view — cut from default surfaces, never from the dataset.
- **Why:** Verified: 84% baseline <5/day, 70% <2/day, 0 corroboration, 5 exposed, severity = z-score so Rugao outranks LA-LB. This single hook is the highest-leverage noise cut in the whole review and it makes P0-1's hero brief *breathe*.
- **Files:** `useMonitorModel.ts`, `DataFeed.tsx`, `Globe.tsx`, `flags.json` (read-only reference)
- **Effort:** **M**
- **Tradeoff:** A looser gate (0.15 / ~17 flags) shows more breadth; a tighter one (0.2–0.25 / 5–8) is cleaner. Recommend shipping the score + a tunable cutoff constant, defaulting ~0.15–0.2, so it's a one-line tweak after eyeballing live.

---

**P0-3 · Size globe flag markers by relevance; dim/drop the noise tail**
*Answers: "super overcomplicated" + "meaningless alerts," on the most central surface.*

- **What:** In `Globe.tsx`, the `flags-ring` layer uses **fixed `getRadius: (d) => d.flag_id===selectedId ? 9 : 7`** (`:502`) and `flags-halo` a **fixed 15px** (`:488-491`) — confirmed all 171 dots are identical size, only `severityColor` tints them. Drive `getRadius` off the **same `relevance` score from P0-2** (e.g. `radius = 5 + relevance*10`), so Hormuz/Shanghai are visibly large and a 0.04-vessel terminal is a small dot — or, below the cutoff, **not drawn** (or rendered as faint low-alpha dust) by default. Add `relevance` to the `GlobeFlag` payload and extend the existing `updateTriggers` (already present for `getRadius` at `:512`).
- **Why:** The globe is the largest element and currently gives "171 equal dots with the needle tinted slightly redder." Size is the most direct triage affordance on a map and it's unused. Marginal effort is tiny once P0-2's score exists.
- **Files:** `Globe.tsx`, `useMonitorModel.ts`
- **Effort:** **S** (given P0-2)

---

### P1 — Sharpen the signal and connect the surfaces

---

**P1-1 · Add a "Top 5 movers" digest under the hero brief**
- **What:** A tight, **fixed-height** "Top movers this week" list immediately under the pinned brief — top 5 by P0-2 relevance, each a single clickable line ("Strait of Hormuz −92% · $65M exposed →") wired to the existing `pickByPortid` (`useMonitorModel.ts:193`, already flies the globe + opens the row). Does **not** scroll away with the rows.
- **Why:** Survey explicitly flags "no top-3/top-5 digest distinct from the raw dump." Fastest path to "get the signal." `pickByPortid` already supports click-to-fly, so wiring is cheap.
- **Files:** `DataFeed.tsx`, `useMonitorModel.ts` — **Effort: S**

---

**P1-2 · Surface "so what / am I exposed" on the collapsed row; de-bloat the expanded row**
- **What:** (a) In the **collapsed** Row (`DataFeed.tsx:334-449`, currently sev + name + kind + spark + metric), inline the one-line "so what" for the 5 exposed flags from `flag.business` (`exposed_value_usd`, `exposed_lanes`, `est_delay_days` — verified present): "$65M / 2 lanes exposed." (b) **De-bloat the expanded row** (`:403-444`): drop the redundant `fr-trendline` **sentence** (trend is shown three ways — inline + sparkline + sentence); **lead with `BusinessImpact`** (currently buried ~9 blocks deep at `:438`); and **render `StormChip`/`OfficialEvent`/`NewsBlock`/`MarketBlock`/`CargoMix`/`NationalDependence` only when populated** — verified empty for 166–171/171, so they're dead "No qualifying coverage found" plumbing today. Put the rest behind one "more detail ▸" expander.
- **Why:** Every surfaced flag should answer "who cares." With the P0 gate in place, most blocks are empty anyway, so hiding empties is nearly free and makes signal rows scannable. Keep the corroboration code — it's the honesty story — just don't let empty-state bloat the row.
- **Files:** `DataFeed.tsx` — **Effort: M**

---

**P1-3 · Group surviving flags into stories**
- **What:** After the gate, cluster the residual rows into named collapsible stories instead of a flat list, by: nearest-chokepoint/corridor; **country** (`portMetaById[...].country` already in the model, `useMonitorModel.ts:149`) → "China: 3 ports softening"; and kind-theme (collapse the 63 low-signal `port_cargo_type_*` flags into one "cargo-mix wobbles" group). Row leaf (`:334-449`) stays. Update the feed count header to "N stories · M ports."
- **Why:** Turns the residual into "a handful of stories." Country is already in the model, so this is mostly rendering. Lower than P1-1/P1-2 because the gate alone already collapses 171→~10.
- **Files:** `DataFeed.tsx`, `useMonitorModel.ts`, `Board.tsx` — **Effort: M**

---

**P1-4 · Rewrite Onboarding to route to the brief; reconcile nav labels; rename "Ledger"**
- **What:** (a) `Onboarding.tsx` currently spends its one guaranteed-attention moment on a philosophy paragraph with an "Explore →" that only dismisses. Replace the body with the live `data.brief.headline` + top 1–2 signal bullets + a **"Read the brief ↓"** button that scrolls to the P0-1 hero. (b) Make `ViewToggle` and `CommandPalette` agree on labels, and **rename the opaque "Ledger §"** to a content-true label (e.g. "Sources") and "Data ⌗" to "SQL." (c) **Remove the standalone `⌘K` chip** (`App.tsx:357-365`) — it advertises the palette that `ViewToggle` already covers; keep `⌘K` as the power accelerator only.
- **Why:** Half of "where is the brief?" is the AI brief living under the least-guessable label, reached via a second nav system that names it differently. Onboarding currently *adds* a step instead of removing one.
- **Files:** `Onboarding.tsx`, `ViewToggle.tsx`, `CommandPalette.tsx`, `App.tsx` — **Effort: S**

---

**P1-5 · Suppress small-base "−100% / +2000%" headlines — require absolute movement**
- **What:** Headlines are templated from `pct_change`, producing misleading catastrophe language ("Escobar LNG +2000%" = ~1 tanker on 0.14/day; "Glasgow 100% below" on 0.18/day). **Primary fix is the Python exporter** that writes `flags.json` (the frontend renders `flag.headline` verbatim in `DataFeed`/`BriefCard`): require ≥ ~3 vessels/day actually moved before a % headline, else phrase absolutely ("~1 fewer tanker call than usual"). **Short-term frontend guard:** rewrite/suppress the % where `baseline < ~3/day` so scary numbers don't render even before the exporter ships.
- **Why:** Verified 51 flags at −100% and 28 > +300%, overwhelmingly small-denominator. False alarms with scary numbers are *worse* than noise — they erode trust in the ~5 real flags. Most of these already fall under the P0 gate; this covers any small-base survivor.
- **Files:** `flags.json` (exporter, out of frontend scope), `DataFeed.tsx`, `BriefCard.tsx` — **Effort: M**
- **Note:** Largely a data-layer fix; frontend's job is to stop foregrounding the % and prefer absolute when base is small.

---

### P2 — Polish: subtract chrome, deduplicate (makes the cleaned signal breathe)

---

**P2-1 · Thin the first-load surface count via progressive disclosure**
- **What:** Trim the ~16 default-`globe` surfaces (`App.tsx:300-606`): (a) collapse the always-open `LayerPanel` (15 rows, 7 niche layers off by default — `layers.gen.ts`) into a single **"Layers"** button that opens on demand (the palette already covers toggling); (b) **show only one time control at a time** — the GFS wind scrubber (`App.tsx:482-496`), the `TimeScrubber` (`:511-537`), and the "History play 2019→now" button can all be on-stage at once with three different time semantics; gate the wind scrubber behind the wind layer being the active focus; (c) collapse the triple-stated thesis (topbar tagline `:312-315` + provenance `:316-321` + Onboarding lede + LayerPanel foot) to one place.
- **Why:** The sourced "super overcomplicated" complaint. Demote, don't delete — every capability stays discoverable, the default screen just gets calm. — **Files:** `App.tsx`, `LayerPanel.tsx`, `layers.gen.ts` — **Effort: M/L**

---

**P2-2 · Deduplicate the stress index and the 6×-repeated disclaimer**
- **What:** Stress is rendered up to 4× — keep `StressGauge → StressDetail` as canonical; make `Board`'s bespoke `fr-board-stress` strip (`Board.tsx:168-189`) reuse `StressGauge`. State the "possibly-related, not a cause" caveat **once prominently** and drop the verbatim repeats in `LayerPanel`, `SignalsRail` (×2), `NearbyPanel`, `Board`, `Onboarding`, topbar.
- **Why:** Pure dedup — removes reconciliation load and disclaimer-as-noise without touching substance or the honesty stance. — **Files:** `StressGauge.tsx`, `Board.tsx`, `SignalsRail.tsx`, `LayerPanel.tsx`, `NearbyPanel.tsx` — **Effort: M**

---

## 4. FIRST 3 CHANGES THIS WEEK

The tightest high-leverage set — each maps to one verbatim complaint, and they compound (the gate makes the hero brief breathe; the score that powers the gate also sizes the globe).

1. **P0-2 — Gate flags to signal (171 → ~5–15).** One derived `relevance`/`isSignal` in `useMonitorModel.ts`, default the feed + globe to it, keep all 171 behind "show all." *Kills the noise the user named; verified to surface exactly the right 5. Effort M.*

2. **P0-1 — Pin the brief expanded, above the feed, lede wired to it.** Default `BriefCard` open, lift it out of `.fr-rows` into a sticky hero, make `.fr-lede` a real button, link the AI brief. *Literal answer to "where is the brief?" Effort M (free of the old height tradeoff once #1 lands).*

3. **P0-3 — Size globe markers by relevance.** Drive `Globe.tsx`'s fixed 7px ring off the #1 score; drop/dim the noise tail. *The globe finally triages at a glance; nearly free once #1 exists. Effort S.*

After these three, the default screen leads with the brief, shows ~10 real flags, and the globe makes the needle bigger than the blips — all three complaints answered in one week. P1 (digest, so-what rows, nav/label fixes, honest headlines) sharpens it; P2 (progressive disclosure, dedup) makes it breathe.
