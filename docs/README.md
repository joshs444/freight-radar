# Freight Radar — docs

Supporting documentation for [Freight Radar](../README.md). The README is the
front door; this directory holds the deeper engineering record.

- **[Architecture Decision Records](adr/)** — six Nygard-format ADRs capturing the
  load-bearing decisions: static committed JSON over a live API, DuckDB as the
  single source of truth, deterministic template prose (no model in the number
  path), cutting the GDELT attention feed, Temporal-for-durability vs the Action
  as production driver, and the deck.gl-on-globe depth fix.
- **[Build plans](plans/)** — the wave-by-wave plans the app was built from
  (mostly shipped), kept for provenance. The active plan is
  [`BEST-IN-CLASS-PLAN.md`](../BEST-IN-CLASS-PLAN.md) at the repo root.

The architecture diagram (the IMF PortWatch backbone → ingest+detect → DuckDB →
publish → static JSON → React globe flow, driven by a Temporal workflow on a
Schedule) lives in the [main README](../README.md#the-one-architectural-seam).

The image assets in this directory (`hero.png`, `flag-detail.png`,
`timescrubber.png`) are the README's screenshots.
