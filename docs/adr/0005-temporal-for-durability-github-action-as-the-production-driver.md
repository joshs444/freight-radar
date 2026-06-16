# 5. Temporal for durability, a GitHub Action as the production driver

Status: Accepted
Date: 2026-06-05

## Context

The refresh pipeline is a multi-step sequence — fetch → detect → attribute →
enrich → assemble → publish — where a mid-run crash must not corrupt or
half-publish the output, and a transient upstream failure should retry rather
than fail the whole run. That is exactly the problem durable-execution engines
like Temporal solve, and demonstrating that pattern is part of this portfolio's
purpose.

But the deployed site is a free static GitHub Pages bundle (see ADR 1). Standing
up a persistent Temporal cluster (server + worker + datastore) just to drive a
**weekly** republish of daily-granularity data would be operational and cost
overkill for the production path, and it would not even run on Pages.

## Decision

Keep **both**, each where it fits:

- **Temporal owns the durability story.** The same fetch → detect → attribute →
  enrich → assemble → publish steps are a real `FreightRadarWorkflow` with a
  `RetryPolicy`, a Schedule, and a dedup ledger
  (`backend/freight_radar/temporal/`). Its crash-durability is **proven
  end-to-end** on Temporal's in-process time-skipping test server: kill the
  worker mid-run and it re-drives from the last completed activity; a second
  identical run makes zero attribution calls via the dedup ledger.

- **A scheduled GitHub Action is the always-on production driver.** `refresh.yml`
  (weekly cron + on-demand) rebuilds the DuckDB from PortWatch, re-runs detection
  and every enricher, commits the changed sidecars, and deploys — running the
  **identical** `publish_static` steps the Temporal activities wrap.

The two paths share the same underlying step functions, so the production driver
and the durable orchestration are not divergent reimplementations.

## Consequences

- Production self-refreshes for free on GitHub's runners, with no persistent
  cluster to host or pay for, matching the static-deploy posture of ADR 1.
- The durable-execution property is real and demonstrable (the kill-the-worker
  resume demo, the dedup-ledger no-op second run) rather than claimed, because
  the workflow is exercised in a test harness on every CI run.
- There are two code paths for "run the pipeline" (the Action's `publish_static`
  and the Temporal workflow). This is an accepted cost; it is bounded because
  both drive the **same** step functions, so behavior cannot silently diverge.

## Amendment (2026-06-09): the step list is now shared code, not a claim

The "cannot silently diverge" consequence above did, in fact, silently diverge:
`publish_static` grew post-export steps (the pooled-FDR signal pool,
claimed-vs-measured, the substrate export, the honesty scorecard, the store
catalog) that no Temporal activity ran, so a Temporal-driven publish shipped
without `signals_fdr.json`, the scorecard, or the catalog. The guarantee is now
structural rather than asserted: `publish.py` defines `PUBLISH_STEPS` — ONE
ordered `(name, step)` registry covering every post-export publish step — and
both drivers iterate it via the same `run_publish_steps()` (`publish_static`
directly; the Temporal `assemble_snapshot` activity after its export). A new
step added to the registry reaches both paths for free, and
`tests/test_publish_steps.py` pins the registry's contents and asserts neither
driver calls a step writer outside it.
