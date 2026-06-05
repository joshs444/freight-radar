# 4. Cutting the GDELT attention feed

Status: Accepted

## Context

A news-attention trend was planned as a soft-corroboration layer: for each active
flag, query GDELT's free DOC 2.0 endpoint for an attention timeline and attach a
sparkline ("attention rising") alongside the existing headlines — strictly
context, never causation. It was designed, built, and tested.

In integration it surfaced a hard operational problem. GDELT's free endpoint
**rate-limits a single IP** so aggressively that it returns HTTP 429 even cold —
within ~180 s of a small burst. The weekly production refresh
(`.github/workflows/refresh.yml`) runs from GitHub Actions' **shared** CI IP,
which is exactly the IP most likely to be throttled. So in production the layer
would be **permanently empty** while burning ~30 s of doomed calls on every
refresh.

## Decision

The GDELT attention layer was **cut** and cleanly backed out of the build. A
permanently-empty, pipeline-polluting feature fails the same honesty bar as a
fabricated one — shipping a layer that is structurally guaranteed to be blank in
production, while slowing the cron, is worse than not shipping it. The decision
and its full reasoning are recorded in
[`../plans/DATA-AUDIT-PLAN.md`](../plans/DATA-AUDIT-PLAN.md) (Phase C2).

Revisit only with a paid or keyed attention source that does not throttle a
shared CI IP.

## Consequences

- The production pipeline carries no layer that is empty by construction, and the
  weekly refresh does not waste ~30 s on calls that are known to 429.
- The judgment is preserved as an artifact rather than silently dropped: the
  "we built it, tested it, and chose not to ship it" reasoning is the point, and
  it lives in `DATA-AUDIT-PLAN.md`.
- The app forgoes a news-attention signal it would otherwise have. The existing
  headline enrichment remains; only the attention *trend* is absent, pending a
  source whose rate limits survive a shared CI IP.
