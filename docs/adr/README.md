# Architecture Decision Records

Each ADR captures one decision already made and shipped in Freight Radar, in
[Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions):
context, decision, consequences. They exist so a reviewer can read the senior
engineering judgment without reading the code.

| # | Decision |
|---|---|
| [1](0001-static-committed-json-over-a-live-api.md) | Static committed JSON over a live API |
| [2](0002-duckdb-as-the-single-source-of-truth.md) | DuckDB as the single source of truth (scope amended 2026-06-09: the measured spine; the sidecar tier is ADR 8) |
| [3](0003-deterministic-template-prose-no-model-in-the-number-path.md) | Deterministic template prose — no model in the number path |
| [4](0004-cutting-the-gdelt-attention-feed.md) | Cutting the GDELT attention feed (partially superseded by the GKG `news_geo` layer) |
| [5](0005-temporal-for-durability-github-action-as-the-production-driver.md) | Temporal for durability, a GitHub Action as the production driver |
| [6](0006-flat-globe-markers-out-of-the-depth-test.md) | Take flat globe markers out of the deck.gl depth test |
| [7](0007-tier-firewall-and-registry-as-single-source-of-truth.md) | The tier firewall + the registry as single source of truth |
| [8](0008-sidecar-store-publish-time-fetch-gated-by-contracts.md) | The sidecar store: publish-time fetch with contracts as the gate |
| [9](0009-committed-jsonl-ledgers-the-system-remembers-itself.md) | Committed JSONL ledgers — the system remembers itself |
