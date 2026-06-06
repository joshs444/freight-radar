# Build plans — a retrospective index

These are the planning artifacts behind the project. The plans below the divider are
**shipped** — the app was built in waves, each plan ending committed, deployed, and
verified live — and are kept for provenance, not as live TODO lists.

The single **active, forward-looking** plan is the **year vision**:
[`STANDPOINT-VISION.md`](STANDPOINT-VISION.md) — evolving the app from a freight globe
into an honest world-awareness platform, with its full free-source catalog in
[`DATA-SOURCES.md`](DATA-SOURCES.md). It is **not yet built** (P0 is the next step). The
prior root plan [`../../BEST-IN-CLASS-PLAN.md`](../../BEST-IN-CLASS-PLAN.md) is now shipped.

For the distilled decisions (rather than the build sequence), see the
[Architecture Decision Records](../adr/).

### 🟢 Active — the forward plan (not yet built)

| Plan | What it covers | Status |
|---|---|---|
| [`STANDPOINT-VISION.md`](STANDPOINT-VISION.md) | The **year roadmap** (P0–P6): typed `LayerDescriptor` registry → two-lane pipeline + capability firewall → full 2065-port spine → measured macro signals → context-ring breadth → honest cross-layer surface. Hub-and-spoke of ownership enforced by construction. From a 10-agent research pass + adversarial critic. | **Active · P0 next** |
| [`DATA-SOURCES.md`](DATA-SOURCES.md) | The free-data catalog behind the vision — **93 sources** across every domain, each tagged measured-vs-context with the statistic we'd own, auth, license, cadence, and license/cost caveats. | Reference (living) |

### ⚪ Shipped — the build history

| Plan | What it covered | Status |
|---|---|---|
| [`PLAN.md`](PLAN.md) | The original wave-by-wave build plan and the verified data contracts (ingest → DuckDB → detect → publish → globe) | Shipped |
| [`FOUNDATION-PLAN.md`](FOUNDATION-PLAN.md) | Five-phase engineering hardening pass (accessibility, rAF→effect refactor, TypeScript-strict migration, reproducible installs, structured logging) | Shipped + verified live |
| [`HISTORY-PLAN.md`](HISTORY-PLAN.md) | The "play through 2019→now" time view that sweeps forward through the shocks | Shipped + verified live |
| [`DATA-LAYERS-PLAN.md`](DATA-LAYERS-PLAN.md) | The external enrichment layers (market context, live storms, hazards, news) as additive sidecars | Largely shipped |
| [`BUSINESS-PLAN.md`](BUSINESS-PLAN.md) | The business-exposure credibility pass — LOCODE routing, carrying-cost correction, the banded cost-of-disruption stack | Shipped |
| [`DATA-AUDIT-PLAN.md`](DATA-AUDIT-PLAN.md) | Turning the 16-finding data audit into a build plan: cargo-aware detection, national-dependence weighting, ETL fail-loud guards — and the documented **cut of the GDELT attention feed** (see [ADR 4](../adr/0004-cutting-the-gdelt-attention-feed.md)) | Shipped (C2 cut) |
| [`COMPLETION-ROADMAP.md`](COMPLETION-ROADMAP.md) | A skeptical, evidence-backed reconciliation (2026-06-03) of "built vs left" across the other plans — a point-in-time audit snapshot; several gaps it flagged (self-refresh, chat, weather, narrative) have since been closed | Historical snapshot |
