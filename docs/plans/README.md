# Build plans — a retrospective index

These are the planning artifacts behind Freight Radar, kept for provenance. Most
are **shipped**; the app was built in waves, each plan ending committed, deployed,
and verified live. They are preserved here as a record of how the project was
reasoned about and built, not as live TODO lists.

The single **active** plan lives at the repo root:
[`../../BEST-IN-CLASS-PLAN.md`](../../BEST-IN-CLASS-PLAN.md).

For the distilled decisions (rather than the build sequence), see the
[Architecture Decision Records](../adr/).

| Plan | What it covered | Status |
|---|---|---|
| [`PLAN.md`](PLAN.md) | The original wave-by-wave build plan and the verified data contracts (ingest → DuckDB → detect → publish → globe) | Shipped |
| [`FOUNDATION-PLAN.md`](FOUNDATION-PLAN.md) | Five-phase engineering hardening pass (accessibility, rAF→effect refactor, TypeScript-strict migration, reproducible installs, structured logging) | Shipped + verified live |
| [`HISTORY-PLAN.md`](HISTORY-PLAN.md) | The "play through 2019→now" time view that sweeps forward through the shocks | Shipped + verified live |
| [`DATA-LAYERS-PLAN.md`](DATA-LAYERS-PLAN.md) | The external enrichment layers (market context, live storms, hazards, news) as additive sidecars | Largely shipped |
| [`BUSINESS-PLAN.md`](BUSINESS-PLAN.md) | The business-exposure credibility pass — LOCODE routing, carrying-cost correction, the banded cost-of-disruption stack | Shipped |
| [`DATA-AUDIT-PLAN.md`](DATA-AUDIT-PLAN.md) | Turning the 16-finding data audit into a build plan: cargo-aware detection, national-dependence weighting, ETL fail-loud guards — and the documented **cut of the GDELT attention feed** (see [ADR 4](../adr/0004-cutting-the-gdelt-attention-feed.md)) | Shipped (C2 cut) |
| [`COMPLETION-ROADMAP.md`](COMPLETION-ROADMAP.md) | A skeptical, evidence-backed reconciliation (2026-06-03) of "built vs left" across the other plans — a point-in-time audit snapshot; several gaps it flagged (self-refresh, chat, weather, narrative) have since been closed | Historical snapshot |
