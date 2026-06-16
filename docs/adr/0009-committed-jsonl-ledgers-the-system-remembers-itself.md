# 9. Committed JSONL ledgers — the system remembers itself

Status: Accepted
Date: 2026-06-09

## Context

The weekly refresh rebuilds the DuckDB warehouse from scratch, so the system
had no durable memory of its own outputs. The adversarial review's one
critical finding fell straight out of that: flag lifecycle
(new/ongoing/escalated/resolved) seeded itself from a `fct_flags` read-back
that was always empty in production — every one of the 168 published flags
said `lifecycle: "new"` forever, hysteresis never damped a wobbling flag, and
a cleared disruption never shipped its resolved tombstone. The same amnesia
blocks any backtest and makes "what did we know last week" unanswerable.

One piece of state already survives rebuilds: `data/state/events_state.json`
is committed (force-added past the `data/` gitignore by the refresh workflow),
and the event timeline it powers has real cross-run history. That pattern
works; per-run warehouse partitions do not — committing Parquet snapshots was
rejected on git-growth math, and the bulk history is already derivable from
git history plus the PortWatch archive.

## Decision

Extend the proven committed-state pattern into three thin, append-only JSONL
ledgers under `data/state/`, force-added by the refresh workflow:

- **`flags_ledger.jsonl`** — one slim line per flag per run (identity,
  geometry, the computed numbers, lifecycle, the one-line headline; never
  `brief_md`). This ledger is the **only** prior-flags source for lifecycle
  (`run_detection._load_prior_flags`); the `fct_flags` read-back is gone, so
  CI, local, and production runs behave identically.
- **`run_ledger.jsonl`** — one line per run: the spine `as_of` (the `run_key`),
  manifest version, stress index, flag count, and a per-layer freshness map
  read from the freshly published sidecars (the record the max-age work reads).
- **`claims.jsonl` + `adjudications.jsonl`** — the adjudication engine's
  ledgers (F4), built on the same append/read core in a later slice.

`freight_radar/ledger.py` owns append/read: appends dedup on
`(run_key, generated_at, flag_id)` / `(run_key, generated_at)` so re-runs are
byte-stable no-ops, and write via temp-file + atomic rename. `run_key` is the
spine `as_of`, which lags and repeats week-to-week, so it does **not** identify a
run — the publish timestamp `generated_at` does. That distinction is load-bearing:
a re-detection that lands on the same `run_key` with revised numbers records its
new state (rather than freezing the first run's), while re-reading the same
published dir still no-ops; and "latest" means the most-recently-appended line,
never `max(run_key)` (a partial upstream fetch can even lower the spine date).
The CLI step
(`python -m freight_radar.ledger ../frontend/public/data`) runs in
`refresh.yml` after the parity gate — never inside `publish_static`, so the
golden-master harness stays a pure function of its fixture inputs.

Growth math (measured 2026-06-16 against the live 186-flag store): ~75KB/week
across both ledgers (~75KB of flag lines incl. the per-row `generated_at`
discriminator + ~1KB run line), against the ~3MB/week the data refresh already
commits in sidecar churn — noise. When a year of lines is worth trimming, rotate
by year (`flags_ledger-2026.jsonl`); nothing rereads old years on the hot path.

**The hard rule:** bulk per-run artifacts (warehouse partitions, Parquet
snapshots, raw fetches) are only ever published via GitHub Releases — never
committed to git. The ledgers stay thin or they don't stay.

## Consequences

- Lifecycle is real in production again: flags can be `ongoing`/`escalated`,
  and a cleared anomaly ships exactly one decayed `resolved` tombstone.
- "What did we know on date X" has a committed, greppable answer, and the
  flags ledger is the substrate for the falsifiable hit-rate record (F4) and
  the event-replay backtest (H2-A).
- A new class of committed state to keep honest: tests must inject throwaway
  state dirs (`FREIGHT_RADAR_STATE_DIR`, enforced by an autouse fixture) so a
  local run can neither read nor pollute production memory.
- If a refresh publishes but its push fails, that run's lines are lost until
  the next run — the ledger is best-effort memory, not a transaction log.
- A resolved tombstone's brief is rebuilt from the slim recorded numbers, not
  the original prose — honest, but terser than the flag it winds down.
- Claims/adjudications are deliberately not in this slice; the ledger core is
  generic so F4 adds files, not rework.
