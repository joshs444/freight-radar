# 2. DuckDB as the single source of truth (local tables only)

Status: Accepted

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
