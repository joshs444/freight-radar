# Freight Radar — Best-in-Class Plan

> **Status: ✅ EXECUTED 2026-06-05 — all three phases shipped + deployed the same day.**
> Commits: `f07986b` (Phase 1: packaging pass + credibility CI gate) · `4801052` + `aa079fb`
> (Phase 2: boot path off the eager critical path, consolidated gate, claim-level chat
> provenance + adversarial refusal eval) · `f8068c1` (WAP), `7c8eefb` (port hierarchy),
> `3506ddb` (history annotations), `9ebfe43` (hero lede + decisive score), `3da07de`
> (ADRs + Mermaid diagram + root tidy) (Phase 3).
> Produced 2026-06-05 from a
> 16-agent benchmark: each of 7 dimensions was researched against the real best-in-class,
> then audited against the actual code + live renders, then synthesized and adversarially
> pressure-tested (the critic re-verified the load-bearing claims against the live repo).
> Respects the non-negotiables throughout: **honesty theme, zero marginal cost,
> free/keyless, public/no-secrets.** Sequenced so cheap credibility fixes land first and
> the enforcement gate exists before the work it's meant to prove.

## Headline

**The substance is already best-in-class — the gap is packaging, enforcement, and
first-30-second legibility**, plus one outright credibility bug and one self-inflicted
metrics wound. A reviewer who reads the code deeply *will* be impressed: the
no-model-in-the-number-path contract is real and code-enforced, the verbatim grounding
eval (190 facts / 39 questions / 0 failures) is stronger than an LLM-judge eval, the
Temporal durability + three fail-loud ETL guards + STL/CUSUM/PELT detection are genuinely
production-grade work, and the README's "How it stays honest" prose is top-tier. The problem is
the 30-second scan never reaches the code — it hits a GitHub About line that says "Live …
dark globe" (the app is light-theme and the whole thesis is *never live*), a README with
no demo link or motion media, test counts that contradict each other, and CI that gates
only frontend lint/build while the backend tests and grounding eval — *the credibility* —
run in no automation at all.

**The three things that most move the needle:** (1) one `gh repo edit` to kill the
"Live … dark globe" contradiction; (2) one consolidated CI gate that runs pytest + the
grounding/parity evals + Lighthouse, converting the strongest artifacts from decorative to
enforced and badge-visible; (3) a README / first-paint relegibility pass so the honesty
moat is visible *before* any code is read.

---

## Already best-in-class — DO NOT churn

These clear the bar. The work below packages/links/enforces *around* them; it does not
touch them.

- **The no-model-in-the-number-path contract** — every figure lifted verbatim via
  `F(value,'src.json')` into `facts[]={v,src}`; display-only formatters never feed facts.
  The load-bearing honesty engine.
- **The verbatim grounding eval** (`check_chat.mjs`) — 190 facts / 39 questions / 0
  failures, exact-match against the real published sidecars. The single most credible
  artifact. Only *add* a refusal block + wire into CI; never weaken to fuzzy match.
- **Temporal durable orchestration + idempotency** — bounded retries, crash-replay,
  `INSERT OR REPLACE` on PKs, week-stable `flag_id`, dedup ledger proven to make zero calls
  on rerun. Hard-won and proven.
- **The three fail-loud ETL guards** — join-coverage gate, fetch-completeness check,
  silent-column-drop refusal, each pinned by deterministic tests. Sharpen into a WAP/DQ
  suite (Phase 3), don't replace.
- **Statistical detection rigor** — STL + held-out rolling z + subtractive CUSUM/PELT
  confirmation (can suppress, never invent), all deterministic-template prose.
- **The two-overlay globe architecture + the depth/blink fix** (`MARKER_PARAMETERS`
  `depthCompare:'always'`/`depthWriteEnabled:false` for the 2-D billboards while the 3-D
  ArcLayer stays depth-tested) + fixed-pixel anti-shimmer radii + no-green / no-auto-rotate
  color discipline + per-layer cited tooltips. Hard-won; any label/declutter work MUST
  preserve these.
- **The lazy()/Suspense split + manualChunks isolation + the a11y foundation** (skip link,
  sr-only globe equivalent, `role=img` alt-text, `:focus-visible` outline, reduced-motion in
  the wind layer). At the bar — only widen the preload filter and add the missing `<main>`.
- **The README honesty/verification prose + the single-amber-accent discipline.** Elevate
  and re-link; do not rewrite.

> **Two audit-brief errors, corrected (don't let them drive churn):** the research brief
> wrongly claimed a "dark globe" and "ZERO on-screen legend." The app is **light-theme** and
> a data-driven legend **already exists** (`.fr-legend`, with the wind chip as a mute
> toggle). Verified in code + screenshots. Extend the legend; never rebuild it.

---

## Phase 1 — Packaging pass + the cheap CI half (a few hours, ~zero architecture risk)

Independent, mostly S-effort, shippable as one PR. **The pure-pytest gate ships here** (not
later) — it's the highest-credibility-per-hour item in the whole audit *and* it protects the
count-reconciliation below from silently regressing.

1. **Fix the GitHub About line — the only outright bug.** One command:
   `gh repo edit joshs444/freight-radar --description "Ocean-freight stress monitor on a 3D
   globe. Every number computed in Python from IMF PortWatch — no model in the number path.
   DuckDB + statsmodels/ruptures detection, durable Temporal loop, React/MapLibre/deck.gl."
   --homepage "https://joshs444.github.io/freight-radar/" --add-topic
   data-engineering,duckdb,temporal,deck-gl,maplibre,anomaly-detection,supply-chain,etl,data-quality`
   (currently: "Live … dark globe", empty homepage, null topics).
2. **Add `LICENSE` (MIT).** GitHub shows a visible "No license" banner on the most-read
   page — same surface as the About bug. Keep IMF PortWatch CC-BY-4.0 + OSM/CARTO credits in
   the README. One file.
3. **Reconcile EVERY test/fact count to the real receipts — read at edit time, do not
   hardcode.** As of today the truth is **76 tests total / 72 non-live**, **190 facts / 39
   questions / 0 ungrounded**, 0 parity mismatches. README currently says "66/66 tests",
   "201 facts", "100+ facts", "20+ questions" (lines 47, 140, 144) — all stale. Pin ONE test
   number and ONE fact number from actual run output and update every location together.
   *(The count already drifted 66→72 since the audit ran — this is why it must be re-read,
   not copied.)*
4. **README lede + demo link.** Restructure: one value sentence → demo GIF (Phase-3 asset,
   placeholder link first) → a two-link row (**Live demo ↗** · **How it stays honest**
   anchor) → *then* "What it is." The 149-line README currently has **no**
   joshs444.github.io link. Fix the two stray "live" uses (L3, L7 alt-text).
5. **Active brief headline** (`brief.py`). Replace the passive noun-phrase
   ("Ocean freight: stress 41.6/100 (high)") with a deterministically-templated active
   conclusion ("Ocean-freight stress is HIGH and rising — Strait of Hormuz is the driver,
   −88% vs normal"). Every value is already in `stress.json`; pure template-string work in
   the number-free prose layer (un-hallucinatable). *This string must exist before the
   Phase-3 hero-lede promotion can use it.*
6. **`tabular-nums`.** Add `font-variant-numeric: tabular-nums; font-feature-settings:'tnum'`
   to the numeric classes (one shared selector). Zero exist in 3,212 lines of CSS today;
   the Space-Mono figures sub-pixel-jitter on every value change. ~10-line diff that
   *reinforces* the honesty thesis (stable numbers read as computed).
7. **Legend size-key.** Extend `.fr-legend` with a small/large amber circle pair labeled
   "vessels/day" and a small/large halo labeled "wind speed", swatch sizes derived from the
   same `sqrtScale`. Size is load-bearing but undocumented. ~20 lines. *Extend, don't
   rebuild.*
8. **Trim the welcome card** to ONE sentence + one action; drop the four bullets. Keep the
   dismiss + localStorage exactly. It currently occludes ~a third of the hero globe.
9. **Persistent provenance chip** near the stress gauge: mono bordered chip "COMPUTED IN
   PYTHON · IMF PORTWATCH · NO MODEL IN THE NUMBER PATH", reusing chip styling. States only
   what's true; turns the constraint into the thing a reader remembers. **Place it near the
   gauge, away from the chat surface** (so it never implies chat *wording* is model-free).
10. **The pytest CI half (S).** New `ci.yml` on push+PR running `uv run pytest -q` (non-live
    set) — the backend tests currently run in *no* workflow. **Prove it with a red→green
    receipt**: push a deliberately-broken fact, watch CI go red, revert — a badge without
    that proof is just a green sticker.

## Phase 2 — Finish the gate, then the two 30-second reads

11. **Complete the consolidated gate (M).** Add to `ci.yml`: `npm run test:chat` +
    `test:parity` (the grounding/parity evals), an **lhci** step, and a **bundle-size
    budget**; wire the two JS evals into `deploy.yml`'s build job and into `refresh.yml`
    after `npm ci`. Have `check_chat.mjs` print a named receipt
    ("GROUNDING EVAL: 190 facts · 39 questions · 0 ungrounded"). Add CI / groundedness /
    Lighthouse **badges** to the README. *Land the Lighthouse step FIRST (even non-blocking)
    so #13's LCP delta is a captured receipt, not an assertion.* Free (public-repo Actions).
12. **Claim-level chat provenance + a refusal block (M).** `facts[]={v,src}` is already
    computed then **discarded** — Chat renders only bare filename chips. Carry `facts[]` into
    `BotMsg`: an expandable "Show evidence (N facts)" drawer (value · source table) + inline
    hoverable number→source chips. Add a **negative/refusal** suite to `check_chat.mjs` (bait
    questions like "what will Hormuz do next week", "exact $ GDP impact") asserting the engine
    routes to HELP / hedges with no fabricated number. First-class tested refusal is the
    staff-AI tell; the eval is currently all happy-path.
13. **Fix the eager critical path (M).** The built `index.html` modulepreloads
    react+vendor+maplibre (~460 KB gz) though the executed boot is ~62 KB gz. (a) Inline/
    relocate the one `ae` symbol the entry pulls from the 130 KB luma/loaders vendor chunk;
    (b) widen vite's `modulepreload.resolveDependencies` filter to also strip
    maplibre+vendor+deck (it strips only weather|geotiff today). **Delete the misleading
    `vite.config.js` comment** that documents the anti-pattern as intentional ("the hero
    deck/maplibre stay preloaded") — or a future reader will "restore" the bug. Re-measure
    LCP against the new Lighthouse gate.

## Phase 3 — Higher-effort credibility builds (now backed by the gate)

14. **Write-Audit-Publish + enumerable DQ suite.** Land each PortWatch pull into
    `stg_*` tables, promote the three guards into a warn/error DQ suite run against STAGING,
    atomic-swap into the prod fact only on pass, surface the DQ verdict + a `lineage_run_id`
    in `manifest.json`. Name it **Write-Audit-Publish** in the README. The guards currently
    fire *after* rows are live — WAP converts "good guards that fire late" into "a pipeline
    that demonstrably refuses to publish bad data." Runs in the Phase-2 CI.
15. **Globe TextLayer + port declutter.** A deck.gl `TextLayer` labeling the top ~6-8
    chokepoints (Suez/Panama/Hormuz/Malacca/Bab-el-Mandeb/Gibraltar/Dover/Bosphorus) via
    `CollisionFilterExtension` (white halo on slate text, auto-hide on overlap/zoom-out), and
    a `CollisionFilter` priority = `vessels/yr` on the 2,065 ports so big ports survive and
    the long tail fades in on zoom. **Preserve the fixed-pixel anti-shimmer radii.** Makes
    the globe self-describing — no TextLayer exists today, so chokepoints are anonymous until
    hover. GPU, zero cost.
16. **History annotation + peak callout.** Render the 3-4 biggest curated event titles as
    on-chart labels at their marker x; add a persistent "you are here vs the 2019→peak (49.3
    on 2026-05-10)" callout; add a "weekly-averaged (live view is daily)" clause so the 47.3
    history-current vs 41.6 live-gauge don't read as an inconsistency. The flagship chart's
    emotional payload is currently invisible unless you press play on the exact right week.
17. **Promote one computed hero lede + a decisive score.** Put the new active headline (#5)
    on the first-paint surface near the gauge; make the score the unmistakable ~42px hero
    with the amber badge as the **only** saturated color in the top band (desaturate ribbon
    arrows). The brief is buried below the "Monitor" header today. *Depends on #5.*
18. **Docs as an engineering record.** Add `docs/adr/` (4-6 Nygard-format ADRs reusing existing
    prose: static-sidecar-over-live-API; DuckDB single source of truth; template-prose / no
    model in number path; cut GDELT; Temporal-for-durability vs the Action driver); upgrade
    the ASCII seam to ONE GitHub-native **Mermaid** diagram; link the strongest Verification
    bullets to the actual test functions on GitHub. **Delete/archive the completed root plan
    docs** (FOUNDATION/HISTORY/etc. are shipped — keep only `DATA-AUDIT-PLAN.md` for the
    GDELT-cut judgment, fold the wave history into ONE retrospective). Fix the two README
    links that would 404 after the move.

## Stretch (each a receipt once the gate exists)

- **Motion GIF/MP4 in the README** (6-10 s: globe + scrubber replaying a real collapse + a
  flag fly-to), encoded < 10 MB with local ffmpeg/gifski, under the H1. The whole "whoa" is
  motion; `docs/` holds only stills. Pair with #4. Zero cost.
- **First-load wow beat** — on first load only (no auto-rotate, skipped under
  reduced-motion), one ~3 s great-circle flyTo to the highest-stress chokepoint, then hand
  control over. Make the feed-row flyTo distance-aware (~900-3000 ms, ease-out).
- **Mobile / touch** *(restored — a first-time visitor on a phone is a real eval path)*:
  hover-only tooltips are unreachable on touch and the legend is 9px — add tap-to-pin
  tooltips and bump touch targets.
- **Suspense globe skeleton** (faint graticule + ghosted dots) replacing the bare
  "acquiring signal…" string + layout-reserving skeletons; unify the brand (favicon radar
  mark → app header, replacing the ◐ emoji).
- **a11y polish** — honor reduced-motion in the history `setInterval` play loop, add the
  `<main>` landmark, audit WCAG 2.2 target-size (24px) + focus-not-obscured.
- **`?debug` per-answer reasoning trace** in the chat (intent_matched, entity_resolved,
  retrieval_keys, facts_pulled, sources) — demonstrates real span/trace observability
  thinking. *(The other vocabulary-driven grab-bag items were cut as low-signal.)*

---

## Do NOT do

- **No local-LLM wording layer in the deployed/CI build.** The one audited item that risks
  both honesty and zero-cost. If explored at all: strictly local, off-by-default,
  re-validated by the grounding gate, OUT of the static deploy — demonstrate via a documented
  local flag + recorded clip only. The live site stays deterministic and $0.
- **No PWA/service-worker that caches data.** A cached snapshot implies live/current data and
  breaks the never-say-live thesis. (Clean do-not — no escape hatch.)
- **No fabricated statistics** — don't invent a confidence interval you don't compute; band
  only the `normal` + scale thresholds you already calculate.
- **No new accent colors to "fix" hierarchy** — the fix for the muddy hero is making amber
  *rarer* (one badge) + Archivo weight, not more hues.
- **No churn of the moat** — the honesty/verification prose, detection substrate, stress
  weighting, the globe internals (two-overlay split, depth fix, fixed-pixel radii), or the
  lazy/Suspense + manualChunks architecture. The work is *around* them.
- **No metered/paid dependency** — Actions (public repo), lhci, GE-on-DuckDB, local
  ffmpeg/gifski, web-vitals are all free/keyless/local. Keep it that way.
