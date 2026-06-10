# Build plans — the index

These are the planning artifacts behind the project, one row per document, each with a
single true status (last reconciled **2026-06-09**). The shipped plans are kept for
provenance, not as live TODO lists. For the distilled decisions (rather than the build
sequence), see the [Architecture Decision Records](../adr/).

## 🟢 Active

| Plan | What it covers | Status |
|---|---|---|
| [`STANDPOINT-VISION.md`](STANDPOINT-VISION.md) | **The active forward plan** — the year roadmap (P0–P6): typed `LayerDescriptor` registry → honesty predicates + capability firewall → agent-legible read surface (MCP + in-browser SQL) → full 2065-port measured spine → measured signal cluster → context-ring breadth → the honest cross-layer surface + the gated DERIVED reasoner. | **P0–P3 ✅ shipped + verified** (registry · honesty half · read surface/MCP/SQL console · 2065-port spine + FDR · 6 signal families). **P4–P6:** headline surfaces shipped early (⌘K palette, lenses, Source Ledger, drift detector, Nearby, comparison matrix, the gated reasoner + `hyp_*` tier); the P4–P5 breadth lists stay a **capacity-bounded menu** under the 5-year plan's layer cap — see the per-phase stamps in §5. |
| [`HARDENING-PLAN.md`](HARDENING-PLAN.md) | Root-cause remediation of the 37-agent adversarial review (104 verified findings): truth reconciliation, production correctness, detection rigor, frontend/provenance surfaces, data depth, tests/CI/supply chain, operability (waves H0–H6). | **In progress** — Wave 0 executing (started 2026-06-09) |

## 🛰 Strategy satellites of the vision

| Plan | What it covers | Status |
|---|---|---|
| [`STANDPOINT-5YEAR.md`](STANDPOINT-5YEAR.md) | The strategic operating doc — depth over breadth, the hard layer cap, the retirement policy, the gated (and mostly fenced) revenue paths. **Precedence: this doc governs strategy; the vision's P4–P5 breadth is a menu under its cap.** | Satellite (living) — Year-1 (H1) items shipped 2026-06-06/07 except Action matrix-sharding |
| [`STANDPOINT-AI-NATIVE.md`](STANDPOINT-AI-NATIVE.md) | The AI-native architecture: one substrate (`fct_observation`), one grounding gate, pooled FDR, the `hyp_*` association tier (firewall-first, dark), the offline fail-closed reasoner. | ✅ Executed 2026-06-07 (Steps 0–9); reasoner truth-stamping tracked as HARDENING H0-H |

## 📚 Living references

| Plan | What it covers | Status |
|---|---|---|
| [`DATA-SOURCES.md`](DATA-SOURCES.md) | The free-data catalog behind the vision — **93 sources** across every domain, each tagged measured-vs-context with the statistic we'd own, auth, license, cadence, and license/cost caveats. | Reference (living) |
| [`EXECUTION-PLAYBOOK.md`](EXECUTION-PLAYBOOK.md) | **How** the vision gets built with agents/ultracode: the gate-driven per-phase loop (scope → plan → build → review → verify → deploy → capture), the workflow patterns per phase type, the "add one layer" micro-loop, and the non-negotiables (verify receipts, CI is the gate). | Reference (living) |
| [`ACCEPTANCE-HARNESS.md`](ACCEPTANCE-HARNESS.md) | **The oracle** — the test-against system that grades every change (agent or human): invariants (honesty CI predicates) · golden masters · adversarial evals (must-refuse bait) · scorecard. | Reference (living) |

## ⚪ Shipped — the build history (chronological)

| Plan | What it covered | Status |
|---|---|---|
| [`PLAN.md`](PLAN.md) | The original wave-by-wave build plan and the verified data contracts (ingest → DuckDB → detect → publish → globe) | ✅ Shipped 2026-06-03 |
| [`BUSINESS-PLAN.md`](BUSINESS-PLAN.md) | The business-exposure credibility pass — LOCODE routing, carrying-cost correction, the banded cost-of-disruption stack | ✅ Shipped 2026-06-03/04 |
| [`DATA-LAYERS-PLAN.md`](DATA-LAYERS-PLAN.md) | The external enrichment layers (market context, live storms, hazards, news) as additive sidecars | ✅ Largely shipped, waves landing 2026-06-03 → 06-06 |
| [`COMPLETION-ROADMAP.md`](COMPLETION-ROADMAP.md) | A skeptical, evidence-backed reconciliation (2026-06-03) of "built vs left" across the early plans | Historical snapshot — its flagged gaps (self-refresh, chat, weather, narrative) have since been closed |
| [`DATA-AUDIT-PLAN.md`](DATA-AUDIT-PLAN.md) | Turning the 16-finding data audit into a build plan: cargo-aware detection, national-dependence weighting, ETL fail-loud guards — and the documented **cut of the GDELT attention feed** (see [ADR 4](../adr/0004-cutting-the-gdelt-attention-feed.md)) | ✅ Shipped 2026-06-04 (C2 cut) |
| [`FOUNDATION-PLAN.md`](FOUNDATION-PLAN.md) | Five-phase engineering hardening pass (accessibility, rAF→effect refactor, TypeScript-strict migration, reproducible installs, structured logging) | ✅ Shipped + verified live 2026-06-05 |
| [`HISTORY-PLAN.md`](HISTORY-PLAN.md) | The "play through 2019→now" time view that sweeps forward through the shocks | ✅ Shipped + verified live 2026-06-05 |
| [`BEST-IN-CLASS-PLAN.md`](BEST-IN-CLASS-PLAN.md) | The 16-agent benchmark pass: packaging, the consolidated CI/grounding/Lighthouse gate, Write-Audit-Publish, globe hierarchy, history annotations, the hero lede, ADRs | ✅ Executed 2026-06-05 |
| [`MONITOR-UX-PLAN.md`](MONITOR-UX-PLAN.md) | Monitor + globe UX from the owner's verbatim feedback: the three-zone scroll fix, the LayerPanel, ship visibility, set-based search + cross-highlight | ✅ Executed 2026-06-05 — its brief default-collapse later reversed by FRONTEND-UX-OVERHAUL P0-1 |
| [`FRONTEND-UX-OVERHAUL.md`](FRONTEND-UX-OVERHAUL.md) | Signal over noise: gate the 171 alerts by relevance, lead with the brief, size globe markers by relevance, honest nav labels | ✅ Executed 2026-06-08 (P0 + P1 core); remaining P1/P2 items folded into HARDENING Wave 3 |
| [`PROVENANCE-AND-CONNECTION.md`](PROVENANCE-AND-CONNECTION.md) | Click-any-datapoint provenance: the registry-fed `<Trace>` chain on flags/signals/ports/context dots, per-bullet brief cites, the two-zone "what's near here" panel, the registry-parity deploy gate | ✅ Executed 2026-06-08 (P0→P2; P2-C stories deliberately cut) |
