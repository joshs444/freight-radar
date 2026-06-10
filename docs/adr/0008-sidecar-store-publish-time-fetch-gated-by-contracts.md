# 8. The sidecar store: publish-time fetch with contracts as the gate

Status: Accepted
Date: 2026-06-09

## Context

ADR 2 makes DuckDB the single source of truth — for the measured spine. The
context/signal ring (storms, quakes, world news, tides, marine, the FRED
families, …) has a different shape: ~25 small upstreams, each either shown
as-is with a citation or reduced to one owned scalar, none needing rolling SQL
history. Routing each through warehouse ingest (a schema, dims, and fact tables
per feed) would multiply the ingest surface for no analytical gain. But the
cheap alternative — fetch at publish time and write a file — has a known
failure mode: an upstream that quietly changes schema or goes empty ships a
silently broken layer.

## Decision

CONTEXT/SIGNAL layers are **publish-time enrichers**: each registry-declared
enricher (`enrich.run_enrichers`, order and membership derived from the
registry per ADR 7) fetches its upstream live during the weekly publish and
writes exactly one JSON sidecar straight into the published store, never
touching DuckDB. A failing enricher degrades to absent — one bad feed never
aborts the publish.

The gate that replaces warehouse discipline is the **data contract**
(`freight_radar/contracts.py`): per sidecar, the required top-level keys, the
item shape the UI actually reads, and a liveness floor. It runs in two lanes:

- **CI:** `tests/test_contracts.py` validates the *committed* sidecars on every
  PR, so a producer whose output drifts fails review;
- **production:** `refresh.yml` runs `python -m freight_radar.contracts
  --demote` over the freshly fetched data — a drifted CONTEXT/SIGNAL sidecar is
  deleted so the layer goes dark, and a `demotions.json` receipt is written
  (the Source Ledger surfaces it), while a broken CORE sidecar
  (snapshot/lanes/flags) hard-fails the run instead.

## Consequences

- A new context layer is one enricher, one descriptor, and one contract — no
  warehouse migration — and the store stays static JSON end-to-end (ADR 1).
- Rot is loud, never silent: drift fails CI or visibly demotes the feed;
  absence (which the frontend already tolerates everywhere) is the designed
  failure state, rather than a plausible-looking broken render.
- Honest costs: sidecars are point-in-time fetches with no local history, so
  the context ring cannot be backtested the way the spine can; publish duration
  and reliability depend on ~25 upstreams (bounded by degrade-to-absent);
  contracts assert *shape + liveness*, never values — a well-formed wrong
  number passes; and not every sidecar is contracted yet, so coverage is a
  floor that has to be grown deliberately.
