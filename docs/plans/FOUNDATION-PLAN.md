# Freight Radar — Foundation Plan (post-audit hardening)

> **✅ COMPLETE — all five phases shipped + deployed + verified live (2026-06-05).**
> 1. **Tooling** — ESLint 9 flat config (react/hooks/jsx-a11y) + Prettier + a CI
>    lint/format gate. 2. **Accessibility** — every icon control is a labelled native
>    `<button>`, the Monitor rows are a valid disclosure (zero interactive-in-interactive
>    nesting), the stress modal is a real `role="dialog"` with focus + Escape, plus a
>    skip-link and a map text-alternative; jsx-a11y interaction rules promoted to errors.
>    3. **Architecture** — the Globe rebuilds its deck layers from a data/selection
>    effect (no idle rAF), and a `useMonitorModel` hook pulled the derivation out of App
>    (463 → 288 lines). 4. **TypeScript** — the whole frontend is strict TS (no `any`, no
>    suppressions) behind a typed `src/types.ts` sidecar contract, with a CI `typecheck`
>    gate. 5. **Backend** — `uv.lock` (+ `eccodeslib` so the wind decode is
>    self-contained) with a uv-based refresh, a package logger that surfaces degraded
>    layers, a shared `_http.py`, and tz-aware timestamps. The remaining items below are
>    documentation of the journey; the boxes are kept for the record.

_Turns the remaining items from the 5-agent best-practice audit (perf · frontend
architecture · a11y/SEO · backend · CI/security) into a sequenced, self-contained build
plan for the **foundational** work: real type safety, clean architecture, full
accessibility, reproducible builds, and tooling. Written to survive a `/compact` — it
embeds the findings + decisions, so it can be executed directly without the audit in
context._

## Status — what's ALREADY shipped (do NOT redo)

The high-ROI audit wins are live on `main` + production:

- **Deploy A (frontend, commit `5474c14`):** Vite `manualChunks` + `React.lazy`
  (Globe/Chat/Upload/StressDetail) → boot JS 631 KB → **15 KB gz**; OpenGraph/Twitter
  cards + 1200×630 `public/og.png`; a11y basics (global `:focus-visible` ring, AA
  `--ink-faint` contrast, removed `maximum-scale`, `prefers-reduced-motion` incl. the
  wind layer, non-blocking fonts); `ErrorBoundary` around the globe; `chunkSizeWarningLimit`.
- **Deploy B (CI + backend, commit `e571374`):** all GitHub Actions bumped to current
  majors (checkout/setup-node/setup-python → v6, configure-pages → v6,
  upload-pages-artifact → v5, deploy-pages → v5; node 22); npm+pip caching;
  `timeout-minutes`; `.github/dependabot.yml`; tenacity retry on the GFS fetch
  (transport-errors only); `tests/test_wind.py`. Verified end-to-end via a dispatched
  `refresh.yml` run.

This plan is the **remaining lower-tier but foundational** work.

## Guiding principles

1. **Incremental + deploy-each-phase.** Every phase ends: tests green (`pytest -m "not
   live"` 70+ · `npm run test:chat` · `npm run test:parity`) + `npm run build` clean +
   headless-verified (0 console errors, globe/wind/ships render, fly-to works) +
   committed + pushed + **live
   receipt** polled past the GitHub-Pages CDN lag.
2. **Never break the live site.** It's the public flagship. Each refactor is verified to
   preserve behaviour before the next. Prefer many small safe commits over one big risky one.
3. **Honesty + free/keyless are unchanged constraints.** No new paid services/keys; the
   "never say live", source-cited, deterministic-number ethos stays.
4. **Foundation = type safety + clean seams.** The point of this plan is that a future
   contributor (or reviewer) sees a typed, linted, well-structured codebase — the
   types lock in the data contracts between the Python publisher and the React reader.
5. **Resume after compact:** re-read this file, then `git log --oneline -25` to see which
   phases are committed; pick up at the first unchecked box.

---

## Phase 1 — Tooling & safety net (do FIRST; everything later leans on it)

A real lint/format/type gate catches the exact bugs the audit named and enforces the
standard for every later edit.

- [ ] **ESLint flat config** `frontend/eslint.config.js`: `@eslint/js` recommended +
  `eslint-plugin-react` + `eslint-plugin-react-hooks` (rules-of-hooks **and**
  exhaustive-deps) + `eslint-plugin-jsx-a11y` (recommended). Add devDeps + `"lint":
  "eslint src"` script.
- [ ] **Prettier** config (match existing style: single quotes, 2-space, ~100 col) +
  `"format"` script; do a one-time format pass (separate commit so the diff is reviewable).
- [ ] **Fix what lint surfaces** (audit named): the dead `SearchBox` import, the
  `useEffect` empty-deps in `Globe.jsx`, deep unsafe optional-chaining in `App.jsx`.
- [ ] **DoD:** `npm run lint` clean, build green, deploy (no functional change), verify live.

## Phase 2 — Accessibility (semantic + keyboard; jsx-a11y now guides it)

The CSS-level a11y (focus ring, contrast, reduced-motion, viewport) is done; this is the
**semantic/operability** tier (WCAG 2.1 AA operable).

- [ ] Convert icon-only / `role`-faked controls to **native `<button>` + `aria-label`**:
  the watch-star (`fr-star` in `DataFeed.jsx` Row), the news-item links, the brief-export
  + csv-export spans, the onboarding close. Native buttons get keyboard + role for free.
- [ ] **Map alternative:** `aria-label` on the globe container + a visually-hidden note
  that the Monitor feed is the keyboard-navigable equivalent; ensure the feed rows
  (already `<button>`) have accessible names.
- [ ] **Skip-link** to the Monitor, visible on focus.
- [ ] **DoD:** `jsx-a11y` lint clean; headless keyboard pass (Tab reaches star/filters/
  chat/feed rows, Enter activates); 0 console errors; deploy + verify.

## Phase 3 — Architecture hardening (in JS, before the TS migration)

Refactor the two god-objects while they're still plain JS (cheaper), then type the clean
result in Phase 4.

- [ ] **Globe.jsx — kill the `rAF` layer-rebuild loop** (audit HIGH). With the wind on
  its own self-animating overlaid overlay and all markers static, the marker overlay does
  NOT need a 60 fps `requestAnimationFrame` tick. Replace it with a data/selection-driven
  `useEffect` (deps: `snapshot, lanes, flags, ships, storms, selectedFlag`) that calls
  `overlay.setProps({ layers: buildLayers(...) })`. The wind overlay (separate, self-animating)
  is untouched. VERIFY: selection highlight updates, data updates render, panning/zooming
  stays flicker-free (no mid-gesture re-instantiation), fly-to works, no idle CPU spin.
- [ ] **Extract `useMonitorModel(...)` hook** (`src/lib/useMonitorModel.js`) from
  `App.jsx`: the `sets`/`rows`/`globeView`/`pickByPortid`/`criticalCount` derivation +
  the flag/scrub memos. Shrinks the ~308-line `App` god-component to an orchestrator.
- [ ] **(Judgment, optional) SelectionContext** to trim `DataFeed`'s ~22-prop signature —
  only if it genuinely reads cleaner; do NOT over-abstract.
- [ ] **DoD:** suite + build green; headless verify the globe behaves identically
  (render, select a flag, pan, fly-to, wind animates, ships+storms show); deploy + verify.

## Phase 4 — TypeScript migration (THE foundational layer; biggest phase — sub-step it)

Full TS for real type safety + a typed contract between the Python publisher and the React
reader. Incremental (`allowJs: true`) so the app builds at every step.

- [ ] **4a — Setup:** add `typescript` devDep + `tsconfig.json` (`strict: true`,
  `allowJs: true`, `checkJs: false`, `jsx: react-jsx`, `noEmit: true`, bundler resolution).
  Add `"typecheck": "tsc --noEmit"` script + run it in `npm run build` (or CI). Vite
  compiles `.tsx` natively — no plugin change.
- [ ] **4b — `src/types.ts` (the foundation):** canonical interfaces for every sidecar
  JSON contract the frontend reads — `Snapshot` (chokepoints/ports incl. `cargo_mix`,
  `avg_vessel_size_dwt`, `share_*`), `Flag` (the 18-key contract + `live_storm`,
  `official_event`, `business`), `Stress`, `World`, `Brief`, `Events`, `Weather`/storm,
  `Ships`/vessel, `Wind`, `Disruptions`, `Gatun`, `Market`, `News`. Mirror the Python
  emitters (`export_snapshot.py`, `detect/detectors.py` `Flag`, `weather.py`, `wind.py`,
  `sidecar/ais_consumer.py`). This is the single source of truth for the data layer.
- [ ] **4c — Migrate `useData.js → useData.ts`** returning a typed `AppData`. Highest-value
  type: everything flows from here.
- [ ] **4d — Migrate `lib/*.js → .ts`** (ask.js, exposure.js, routing.js, csv.js, colors.js,
  format.js, trend.js, windLayer.js, useMonitorModel.js, exporters.js, useWatchlist.js).
- [ ] **4e — Migrate `components/*.jsx → .tsx`** (props interfaces from `types.ts`).
- [ ] **4f — Migrate `App.jsx → App.tsx` and `Globe.jsx → Globe.tsx`** last (most complex;
  type the deck.gl/maplibre imperative code, the dual-overlay refs).
- [ ] Tighten `tsconfig` as coverage grows (eventually drop `allowJs`).
- [ ] **DoD (per safe batch):** `npm run typecheck` clean + build green + app works
  (headless). Deploy in 2–3 safe batches (e.g. after 4c+4d, after 4e, after 4f), verify
  live each time. Keep `test:chat` + `test:parity` green throughout.

## Phase 5 — Backend reproducibility & hygiene (independent; any time)

- [ ] **`uv.lock`** — `uv lock` (hash-pinned) committed; switch `refresh.yml` install to
  `uv sync --extra wind` (or `pip install --require-hashes`). Reproducible, faster CI.
- [ ] **Structured logging** — replace failure-path `print()` with `logging.warning`
  across `sidecar/ais_consumer.py`, `weather.py`, `hazards.py`, `gatun.py`, `wind.py`;
  configure a package logger. Stop `|| echo` from silently swallowing the wind decode in CI
  (log it but keep non-fatal).
- [ ] **Shared HTTP resilience** — a `freight_radar/_http.py` retry+timeout helper (mirror
  wind.py's transport-only retry) applied to the other live fetchers
  (`weather`/`hazards`/`gatun`/`market`/`news`) so a transient blip can't silently drop a
  weekly layer.
- [ ] **Hygiene** — tz-aware UTC datetimes; fix `asyncio.get_event_loop()` +
  `out_dir: Path = None` deprecations for 3.13/3.14.
- [ ] **DoD:** `pytest -m "not live"` green; a dispatched `refresh.yml` run succeeds; verify.

---

## Sequencing & rationale

| Phase | What | Why this order | Risk |
|---|---|---|---|
| 1 | Tooling (eslint/prettier/typecheck gate) | Catches issues + enforces standard for all later edits | Low |
| 2 | Semantic + keyboard a11y | `jsx-a11y` lint (Phase 1) now flags exactly these | Low–Med |
| 3 | Architecture refactor (rAF→effect, extract hooks) | Cheaper to refactor in JS; gives TS a clean target | Med (globe) |
| 4 | **TypeScript migration** | Type the *clean* code + the data contracts = the real foundation | Med (large, but incremental) |
| 5 | Backend reproducibility/hygiene | Independent of the frontend; slot anywhere | Low |

**Order = 1 → 2 → 3 → 4 → 5.** Phase 5 is parallel-safe (backend-only) and can be pulled
forward if desired. The frontend phases are sequential: lint before a11y, refactor before
typing (so we don't type then re-shape).

**Definition of done (whole plan):** lint + typecheck + 70+ tests + chat + parity all
green in CI; the app is fully TypeScript with a typed sidecar contract; every interactive
control is keyboard-operable and labelled; the globe has no idle frame loop; the backend
build is reproducible (uv.lock) and logs its degradations. Each phase deployed + verified
live along the way.
