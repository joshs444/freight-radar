# Standpoint — Agentic Execution Playbook

_How the [year vision](STANDPOINT-VISION.md) actually gets built: the repeatable agentic loop
that turns a phase's gates into shipped, tested, deployed code. The "can we execute it with
agents / ultracode?" answer — **yes**, and here's the recipe._

## Why the plan is agent-executable by design

Two properties make it safe to hand a phase to agents:

1. **It's gate-driven, not vibe-driven.** Every phase has explicit, *machine-checkable* exit
   criteria — the MVS add-a-layer loop, the golden crosswalk (incl. **known non-joins**), the
   tier predicates, "still passing contract checks after 8 weeks." An agent builds **to a gate**
   and CI proves done; there is no "looks finished."
2. **The unit of work is one append.** Once P0's `LayerDescriptor` registry exists, adding or
   modifying a layer is one descriptor + one enricher + CI — an agent-sized task: small,
   isolated, verifiable. Most of the year decomposes into a loop an agent can run end-to-end.

The honesty brand is what makes agent output *trustworthy*: the structural firewall + per-row
tier/lineage + the causal-verb lexicon mean an agent (building **or** reasoning) literally cannot
merge something that breaks the brand.

## The per-phase loop

Each P0–P6 phase runs the same loop — sequential where steps depend, parallel + worktrees where
streams are independent.

| Step | Tool | What |
|---|---|---|
| 1. **Scope** | `Explore` agent / inline read | Read the relevant code 3-layer (backend ↔ frontend ↔ CI); produce the work-list. |
| 2. **Plan** | `Plan` agent / a design **Workflow** | Turn the phase's vision goals + the §11 gates into a tactical plan whose acceptance criteria **are** the gates. Design-heavy phases → a judge-panel (N approaches → score → synthesize) + an adversarial critic. |
| 3. **Build** | main session orchestrates + parallel agents / **git worktrees** | Implement. Isolated worktrees for independent edit streams that would conflict; sequential for dependent ones. |
| 4. **Review** | adversarial-verify **Workflow** + `/code-review` | Dimensions → find → adversarially verify each finding (subagents lie — demand receipts). `/code-review` on the diff. |
| 5. **Verify** | `/verify` · `/run` · headless smoke · **CI** | Real runtime receipts, never assertions. CI is the authoritative gate (the local full pytest hangs on the Temporal tests — rely on CI). |
| 6. **Deploy** | weekly Action / Pages | Deploy is part of done; verify the live receipt. Undeployed = not done. |
| 7. **Capture** | plan + memory update | Fold learnings back into the plan; the phase's gate becomes a permanent CI predicate. |

## Workflow patterns mapped to phase types

- **Research / discovery** (source scouting, P3–P5) → *multi-modal sweep*: parallel scouts by
  domain → merge. _Already run: the 93-source catalog._
- **Design / architecture** (P0 registry, P2 schema) → *judge panel* (N designs → score) +
  *adversarial critic*. _Already run: the substrate + temporal reframes, and the three review
  passes in the vision doc._
- **Migration / sweep** (P0 refactor across files; P2 2065-port spine) → *pipeline*: discover
  sites → transform each in a worktree → verify, loop-until-clean.
- **Review** → *adversarial verify* (N skeptics per finding; kill on majority-refute) +
  `/code-review`.

## Non-negotiables (the execution brand)

- **Verify every receipt — subagents lie.** Demand runtime proof; never trust a claimed result.
- **CI is the gate.** The honesty invariants (tier predicates, import-graph firewall, causal-verb
  lexicon, freshness, crosswalk non-joins, contract-checks-after-8-weeks) are CI predicates —
  **green CI is the definition of done.**
- **Worktrees for parallel edit streams; sequential for dependents.** Use parallelism where
  streams are genuinely independent — never force it.
- **Don't jump the queue.** Foundation before features (the dependency order in §5). The boring
  80% first; the reasoning agent and cross-layer surface **dead last**.
- **No secrets in the repo; no metered APIs.** The zero-marginal-cost gate is itself a CI check.

## The smallest unit: the "add one layer" micro-loop (post-P0)

This is the loop the whole year is built on — and it's agent-sized:

1. append a `LayerDescriptor` (id, kind, source, refresh, render, honestyNote);
2. write one enricher (`run(ctx)` → sidecar, degrade-to-absent) — or one WAP fact for SPINE/SIGNAL;
3. CI proves: tier predicate · source/license · bitemporal stamps · lineage · firewall · TS
   parity · causal-verb lexicon · (for measured) FDR + numeric-correctness;
4. `/code-review` → `/verify` (headless) → deploy → live receipt;
5. the layer is live — or CI is red and **nothing shipped.**

When that loop is **boring and safe** (the P0–P1 milestone), an agent can run it. At that point
"do it all" becomes a queue of small, verified appends — executed in the priority order the
vision sets, one shippable layer at a time.

---

_This playbook is not aspirational: the vision it executes was itself produced by it — research
sweeps, design passes, adversarial critics, then built-tested-deployed layers with headless
verification and live receipts, each captured back into the plan. The method is the thing that
wrote the map._
