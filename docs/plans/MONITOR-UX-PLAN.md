# Monitor + Globe UX Plan

> **Status: ✅ EXECUTED 2026-06-05 — shipped + deployed the same day.** Commits: `db30e23`
> (three-zone scroll fix + brief default-collapse — *the collapse half was later reversed;
> see the note at Phase 1 item 1*) · `64495f7` (LayerPanel layer control) · `4acd24b`
> (ship visibility — reorder + bump; *item 6's heading-chevron glyphs were deferred in
> that commit and remain unbuilt*) · `3a47e22` (set-based search + two-way
> cross-highlight) · `0876730` (the "near N of 28 chokepoints" honesty line).
> From a 5-agent deep review of the
> owner's verbatim feedback, benchmarked against best-in-class alert/issue panels + map
> trackers and adversarially pressure-tested. Every structural claim was verified against
> the actual code. Respects the non-negotiables: **honesty** (ships are a near-chokepoint
> sample, never "all ships"/"live"), **zero marginal cost** (all data already in the loaded
> sidecars), the **globe depth-fix** (`MARKER_PARAMETERS`), and no shimmer (pixel-fixed
> markers, no looping pulses).

## The verbatim asks → what's actually wrong

| You said | Root cause (verified in code) |
|---|---|
| "can't scroll down to see all the issues, I just see the stuff on top" | `.fr-feed` is a flex column whose **only** scroll region is `.fr-rows` (`flex:1`). The brief card (default **open**), search, hazards, upload CTA, and the "Your exposure" block all stack **above** it and eat the height — the critical issues end up below the fold. |
| "see the ships more" | Ships render **before** the amber chokepoints in the layer array → the big amber discs **paint over** the 119 vessels clustered on the same coordinates. And `heading` (collected for all 119) is used only in the tooltip — every ship is an identical dot. |
| "easily turn the wind on and off" | The wind toggle is the only control in the legend but is styled `border:0; background:none` — visually indistinguishable from the static caption text next to it. |
| "do we see all the ships or just at the ports?" | Neither — and that answer isn't surfaced anywhere the user looks (see Honest-answer below). |
| "highlight / search for different things … understand what's going on" | Search is **name-only** (country / cargo / severity / kind are in the data but discarded); cross-highlight is one-way and flag-only; layers can't be toggled or soloed. |

**The honest answer to "all ships or just at ports?", surfaced in-app:** *"Real AIS vessel
positions **sampled near the 28 monitored chokepoints** — a point-in-time snapshot at publish,
**not all ships, and not the ~2,000 ports**" (119 vessels now; source aisstream.io).* The live
type mix is **112 generic vessel / 4 cargo / 3 passenger / 0 tanker** — so the legend's teal
"ship" swatch is honestly just "vessel."

---

## Phase 1 — Quick wins (S-effort, independent, each dents a distinct complaint) — do first

1. **Default-collapse the brief, keep its headline as the always-on "what's going on" line.**

   > **⚠ Superseded 2026-06-08 by [FRONTEND-UX-OVERHAUL.md](FRONTEND-UX-OVERHAUL.md) P0-1**
   > (commit `5718cf0`): the brief now defaults **OPEN**. The collapse existed to protect
   > the feed's height; once the feed was gated to ~signal-only rows there was room for
   > both, and the brief — the verbatim "where is the brief?" answer — leads. The code
   > follows the later plan (`BriefCard.tsx`).

   `BriefCard.tsx` `useState(true)` → `false`, persisted via `localStorage 'fr_brief_open'`
   (mirrors `fr_wind_off`). Collapsed = a single clickable row showing the kicker + the
   computed stress headline (already in `.fr-brief-top`). This reclaims most of the
   above-the-fold height **and** explicitly keeps the one-line state-of-the-world summary
   visible — so collapsing answers "understand what's going on," it doesn't remove it.
2. **Make the wind toggle look like a control** (interim, until the LayerPanel below
   supersedes it): give `.fr-legend-toggle` a real chip border/background + an on/off pill.
   ~10 lines of CSS; "easily turn the wind on/off" becomes true immediately.
3. **Make ships visible: reorder + bump.** Move the `ships-glow`/`ships` layers to render
   **after** `choke` in `buildLayers`; raise the core radius 3 → ~4 and glow alpha 48 → ~70.
   Keep pixel-fixed radii + `MARKER_PARAMETERS`. **Verify the chokepoint discs stay readable
   after the reorder** (reordering can invert the occlusion — the owner needs both).

## Phase 2 — The scroll fix + the layer system (M-effort, the must-do core)

4. **Three-zone Monitor restructure (the scroll fix).** In `DataFeed.tsx`/`styles.css`, split
   `.fr-feed` into: a **sticky header** (`.fr-feed-head` + search + `.fr-filters`, pinned,
   never scrolls), **one scroll body** (`.fr-rows`), and the **fixed footer**. Move BriefCard,
   Hazards, Upload, and the Exposure block to be the **first children inside `.fr-rows`** so
   they scroll *with* the issues instead of starving them. Net: the issues become the
   dominant, always-reachable surface; controls stay put. **Re-verify against the 3 existing
   mobile `@media` overrides** (`position:sticky` behaves differently when the panel becomes a
   full-width bottom sheet).
5. **LayerPanel — replace the passive legend with a real control.** One card, one row per
   overlay — **ports (2,065) · chokepoints (28) · ships (119) · storms · flags · lanes ·
   wind** — each with a swatch, a **live count** (all already in `data`), and an on/off
   switch. Lift a `Record<LayerId, boolean>` in `App.tsx` (migrate `fr_wind_off` into it),
   gate each layer in `buildLayers`. The **ships row carries the honest scope line** verbatim
   ("sampled near the 28 chokepoints — not all ships, not the ~2,000 ports") + source +
   `generated_at`, and the swatch is relabeled **"vessel."** This is the single most important
   honesty copy — it directly answers your question where you'll see it.
6. **Heading-oriented ship glyphs (default to the verifiable path).** Render vessels as a
   **heading-rotated chevron via `PathLayer`/`PolygonLayer`** (`getAngle`/rotated path from the
   existing `heading`) so they read as *ships going somewhere*, distinct from round dots —
   **and this path renders under the headless SwiftShader tool so I can verify it.** deck's
   `IconLayer` (prettier arrowhead) is a *verify-in-a-real-browser-then-upgrade* option, not
   the default. No looping pulse (shimmer risk); a one-shot scale-in is the ceiling. Honesty:
   heading is a **static published bearing, not a live track** — no motion trails.

## Phase 3 — Search, highlight, comprehension (M-effort)

7. **Two-way hover cross-highlight** (enabling infra for search): lift `hoveredId` in `App`;
   row hover ↔ a `portid`-keyed highlight ScatterplotLayer (with `MARKER_PARAMETERS`); deck
   hover → row pulse. Framed as the substrate the next item reuses, not a standalone feature.
8. **Set-based, multi-field search.** Enrich the search index with country / cargo / kind /
   severity; a tiny token parser (`country:` / `cargo:` / `kind:` / `is:critical`, bare terms
   match name+country+cargo). A multi-match **lights all matching marks on the globe and dims
   the rest** (reusing #7's layer) with a **result-count chip and a first-class Clear** — so
   "search for different things" is iterative and easy to reset. Keyless, client-side.
9. **Count-bearing, severity-emphasized filter chips** (medium): per-filter counts on the
   All/Critical/Chokepoints/Ports chips; the Critical chip gets the amber active state.

## Stretch (optional, after the core)

- **Layer solo / focus-and-dim** in the LayerPanel (click a row → dim the others to ~25%
  alpha via the existing `rgba` helper) — the "better system for understanding" taken further.
- **Overflow affordance** on `.fr-rows`: a bottom fade + "showing N of M — scroll for more"
  so a long critical list never hides silently.
- **Affirmative all-clear** empty state for the Critical filter ("All clear — no critical
  flags right now") instead of the generic empty text.
- **"Near N of 28 chokepoints right now"** — the 119 vessels actually cluster near a handful
  (Øresund/Dover/Bosphorus/Suez); computing the live coverage client-side is the *most* honest
  version of the answer. Zero cost.
- **Region/cargo quick-filters + a Cmd-K palette** — region needs a one-line backend
  country→region map (the **only** item touching the data pipeline), so it's genuinely last.

## Do NOT do

- **Honesty:** never imply "all ships," "live/real-time," or ships at the 2,065 ports. Every
  ship surface carries the verbatim note. Heading is a static bearing — no motion trails. The
  type mix is sampled and **varies per refresh**, so prefer the single honest "vessel" label
  (or derive the key from the types actually present) over a hardcoded multi-color key.
- **Zero cost:** no paid tiles/feeds/services, no new fetches — every count/field is already
  in the loaded sidecars. Numbers stay computed in Python.
- **Don't break the globe:** every marker keeps `MARKER_PARAMETERS`; the 3-D ArcLayer keeps
  depth; markers stay pixel-fixed; no looping pulses (the old blink class).
- **Don't merge the IconLayer glyph without real-browser verification** — ship the
  SwiftShader-renderable chevron path; treat IconLayer as an upgrade.
- **Don't over-build:** the scroll fix is a contained zone-restructure + a BriefCard one-liner
  — no panel rewrite, no virtualized list, no new state library. Don't touch the
  sidecar/deck.gl architecture.
