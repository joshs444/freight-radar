# 2. DuckDB as the single source of truth (local tables only)

Status: Accepted (scope amended 2026-06-09 — see below)
Date: 2026-06-05

## Context

The pipeline ingests from multiple upstreams (IMF PortWatch via ArcGIS REST, and
optional garnish feeds). Detection needs rolling baselines over 120+ days of
history per entity — window functions over a non-trivial amount of daily data.
The publish step then reads that history to assemble snapshots and flags.

Two failure modes have to be designed out: (1) different parts of the app
reading from different places (a snapshot computed off the live API while a flag
is computed off a cached frame) producing inconsistent numbers; and (2) a
publish that reaches back out to an upstream at render time, coupling the output
to the upstream's availability.

## Decision

A single local **DuckDB** file (`data/freight_radar.duckdb`) is the only thing
the detection and publish code reads from. Ingest is the **only** writer to it.
Everything downstream — `export_snapshot.py`, the detectors, every enricher —
runs SQL against the local `dim_*` / `fct_*` tables and **never reaches an
upstream directly**. DuckDB was chosen because it is a single embedded file (no
server to run), and its window functions express the rolling-baseline math
(STL residual → rolling z, normal-throughput percentiles) directly in SQL.

This is the project's "one architectural seam": ingest writes the warehouse, and
the warehouse is the only source of truth for everything that follows.

## Consequences

- All published numbers are internally consistent because they are all derived
  from one committed snapshot of one local table set, not from N live reads that
  can disagree.
- Detection's rolling baselines, percentile-of-normal, and per-cargo-type splits
  are plain SQL window functions over a single file — no external store, no
  query service, nothing to provision.
- The publish step has **zero upstream dependency at render time**: once the data
  is in DuckDB, the rest of the pipeline runs offline and deterministically.
- The committed DB is gitignored and rebuilt fresh on each refresh, so the
  warehouse is reproducible from source rather than a hand-maintained artifact.

## Scope amendment (2026-06-09)

As originally written, "Ingest is the **only** writer" and "every enricher …
**never reaches an upstream directly**" claim more than the system does. Three
things were never DuckDB-mediated:

- detection itself writes back into the warehouse — `run_detection` upserts
  `fct_flags` (a second writer, inside the trust boundary);
- the publish step `CREATE OR REPLACE`s the substrate index tables
  (`dim_entity` / `fct_observation`, `substrate.py`) as it runs;
- the CONTEXT/SIGNAL enrichers **fetch their upstreams live at publish time**
  and write JSON sidecars that never pass through DuckDB at all.

The honest scope of this decision: **DuckDB is the single source of truth for
the measured PortWatch spine** — every number derived from PortWatch history
(detection baselines, snapshots, timeseries, the stress index) reads from the
one local file, and the publish of that spine has zero upstream dependency at
render time. The sidecar tier is a deliberately different pattern —
publish-time fetch, gated by data contracts — recorded as its own decision in
[ADR 8](0008-sidecar-store-publish-time-fetch-gated-by-contracts.md).
