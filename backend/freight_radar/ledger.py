"""Committed JSONL ledgers under ``data/state/`` — the system's memory of itself.

The weekly refresh rebuilds the DuckDB warehouse from scratch, so every table is
amnesiac: ``fct_flags`` only ever holds the current run, lifecycle labelling saw
an empty prior state in production, and "what did we know last week" was
unanswerable. These thin, force-added JSONL ledgers (the proven
``events_state.json`` committed-state pattern — ADR-0009) give the pipeline a
durable run-over-run memory without committing bulk per-run artifacts:

    flags_ledger.jsonl   one slim line per flag per run — identity, geometry,
                         the computed numbers, lifecycle, and the one-line
                         headline; never ``brief_md`` (the prose bulk). The ONLY
                         prior-flags source for lifecycle labelling
                         (``run_detection._load_prior_flags``).
    run_ledger.jsonl     one line per run: spine ``as_of``, manifest version,
                         the stress index, flag count, and a per-layer freshness
                         map read from the freshly published sidecars.

``run_key`` is the spine ``as_of`` date — data-derived, so it can repeat (two
refreshes in a week land on the same lagging PortWatch date, the common case)
and is not unique to a run. A run is identified by ``(run_key, generated_at)``
— the publish timestamp — so re-reading the same published dir is a byte-stable
no-op while a genuine re-detection that shares a run_key still records its
revised flag state instead of silently freezing the first run's numbers (dedup
on ``(run_key, generated_at, flag_id)`` / ``(run_key, generated_at)``; "latest"
means most-recently-appended, never ``max(run_key)`` — the spine date can even
regress on a partial upstream fetch). Appends rewrite the file via a temp file
+ atomic rename, so a crash mid-append can never leave a torn ledger. The
append/read core is generic on purpose: the F4 ledgers (``claims.jsonl``,
``adjudications.jsonl``) reuse it without rework.

CLI (refresh.yml runs this after the parity gate, before the data commit;
appends live here, never inside ``publish_static``, so the golden harness stays
deterministic)::

    cd backend && uv run python -m freight_radar.ledger ../frontend/public/data
"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Callable, Hashable, Iterable

from .config import DATA_DIR

FLAGS_LEDGER = "flags_ledger.jsonl"
RUN_LEDGER = "run_ledger.jsonl"

# The slim per-flag line: identity + geometry + the computed numbers + the
# one-line headline (a resolved tombstone republishes it as "[Resolved] ...").
# brief_md is deliberately excluded — it is ~0.7KB of prose per flag and is
# reconstructible from these numbers (see _slim_brief).
FLAG_FIELDS = (
    "flag_id", "kind", "portid", "entity", "lat", "lon", "severity",
    "lifecycle", "zscore", "value", "baseline", "pct_change", "metric",
    "as_of", "headline",
)


def state_dir() -> Path:
    """The committed-state dir (``data/state/``), env-overridable like the DB path.

    Tests inject throwaway dirs through ``FREIGHT_RADAR_STATE_DIR`` so a local
    run can never touch the real committed ledgers.
    """
    return Path(os.environ.get("FREIGHT_RADAR_STATE_DIR", str(DATA_DIR / "state")))


# --- generic JSONL core (shared by every ledger, including F4's later ones) ---


def _read_jsonl(path: Path) -> list[dict]:
    """All records in a JSONL ledger, oldest first. Missing file -> [].

    A malformed line (e.g. a torn write from a crashed pre-atomic tool) is
    skipped rather than poisoning the whole ledger.
    """
    if not path.exists():
        return []
    records: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return records


def _append_jsonl(path: Path, records: Iterable[dict], key: Callable[[dict], Hashable]) -> int:
    """Append ``records`` dedup'd on ``key``; returns how many were actually new.

    Idempotent: a record whose key is already in the ledger (or duplicated within
    this batch) is dropped, so re-running an append is a no-op and the file is
    byte-stable. The whole ledger is rewritten to a temp file in the same dir and
    atomically renamed over the original — a crash can never leave a torn line.
    """
    existing = _read_jsonl(path)
    seen = {key(r) for r in existing}
    new: list[dict] = []
    for r in records:
        k = key(r)
        if k in seen:
            continue
        seen.add(k)
        new.append(r)
    if not new:
        return 0
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "".join(json.dumps(r, separators=(",", ":")) + "\n" for r in existing + new)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(body)
        os.chmod(tmp, 0o644)  # mkstemp defaults to 0600; these are committed files
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return len(new)


# --- append API ---------------------------------------------------------------


def append_flags(
    run_key: str, flags: Iterable[dict], state: Path | None = None, *, generated_at: str | None = None
) -> int:
    """One slim line per flag for this run; dedup on (run_key, generated_at, flag_id).

    ``generated_at`` (the run's publish timestamp) is what tells a genuinely-new
    detection apart from an idempotent CLI re-run: re-reading the same published
    dir carries the same generated_at, so the append no-ops byte-for-byte; a fresh
    refresh that lands on the SAME spine ``as_of`` (the common weekly case — the
    spine date lags and repeats) carries a new one, so its revised flag state is
    recorded rather than dropped on the floor against the stale row. run_key alone
    is not unique per run.
    """
    records = [
        {"run_key": run_key, "generated_at": generated_at, **{k: f.get(k) for k in FLAG_FIELDS}}
        for f in flags
    ]
    return _append_jsonl(
        (state or state_dir()) / FLAGS_LEDGER,
        records,
        key=lambda r: (r["run_key"], r.get("generated_at"), r["flag_id"]),
    )


def append_run(record: dict, state: Path | None = None) -> bool:
    """One line per run; dedup on (run_key, generated_at). True iff newly recorded.

    Like the flags ledger, generated_at — not run_key — identifies a run: two
    refreshes can share a spine ``as_of``, so a re-detection with revised numbers
    records a new run line while an idempotent CLI re-run no-ops.
    """
    return (
        _append_jsonl(
            (state or state_dir()) / RUN_LEDGER,
            [record],
            key=lambda r: (r["run_key"], r.get("generated_at")),
        )
        > 0
    )


# --- read API -------------------------------------------------------------------


def read_flags(state: Path | None = None) -> list[dict]:
    return _read_jsonl((state or state_dir()) / FLAGS_LEDGER)


def read_runs(state: Path | None = None) -> list[dict]:
    return _read_jsonl((state or state_dir()) / RUN_LEDGER)


def latest_run(state: Path | None = None) -> dict | None:
    """The most-recently-RECORDED run line — by append order, never ``max(run_key)``.

    run_key is the spine ``as_of``, a data-derived date that can repeat (two runs
    in a week) and can even regress (a partial upstream fetch lowers the max date),
    so the latest run is the LAST one written, not the lexicographically-greatest
    run_key. The run ledger is authoritative (it records a run even when zero flags
    fired); callers fall back to the flags ledger when only flag lines exist.
    """
    runs = read_runs(state)
    return runs[-1] if runs else None


def latest_run_key(state: Path | None = None) -> str | None:
    """The run_key of the most-recently-recorded run (append order)."""
    run = latest_run(state)
    if run is not None:
        return run.get("run_key")
    flags = read_flags(state)
    return flags[-1].get("run_key") if flags else None


def prior_flags(state: Path | None = None) -> dict[str, dict]:
    """The latest run's still-active flags keyed by flag_id, for lifecycle seeding.

    Matches what ``detect/lifecycle.py`` expects from the old ``fct_flags``
    read-back: rows from the LATEST run only — identified by its
    ``(run_key, generated_at)`` so a re-detection sharing a spine date seeds from
    the NEWER run, not the stale one — excluding that run's ``resolved`` tombstones
    (so a cleared flag doesn't keep re-resolving), each carrying every field
    ``apply_lifecycle`` touches — ``brief_md`` is reconstructed from the slim
    numbers since the ledger deliberately drops the prose. Empty dict on the first
    ever run.
    """
    run = latest_run(state)
    if run is not None:
        rk, gen = run.get("run_key"), run.get("generated_at")
    else:  # a state dir with only flag lines: anchor on the last-recorded flag's run
        flags = read_flags(state)
        if not flags:
            return {}
        rk, gen = flags[-1].get("run_key"), flags[-1].get("generated_at")
    out: dict[str, dict] = {}
    for r in read_flags(state):
        if r.get("run_key") != rk:
            continue
        if gen is not None and r.get("generated_at") != gen:
            continue
        if r.get("lifecycle") == "resolved":
            continue
        out[r["flag_id"]] = _as_prior_row(r)
    return out


def _as_prior_row(r: dict) -> dict:
    """A ledger line widened to the prior-row shape lifecycle.py consumes."""
    row = {k: r.get(k) for k in FLAG_FIELDS}
    row["entity"] = row["entity"] or row["portid"]
    row["headline"] = row["headline"] or f"{row['entity']} {str(row['kind']).replace('_', ' ')}"
    row["brief_md"] = _slim_brief(row)
    return row


def _slim_brief(row: dict) -> str:
    """A minimal honest brief rebuilt from the slim ledger numbers.

    Only a resolved tombstone ever republishes this (lifecycle re-emits a cleared
    flag once with decayed severity); every figure is the real number the ledger
    recorded for that flag, nothing invented.
    """
    parts = []
    if isinstance(row.get("value"), (int, float)):
        parts.append(f"was at **{row['value']:g}**")
    if isinstance(row.get("baseline"), (int, float)):
        parts.append(f"vs a norm of ~{row['baseline']:g}")
    if isinstance(row.get("zscore"), (int, float)) and isinstance(row.get("pct_change"), (int, float)):
        parts.append(f"({row['pct_change']:+g}%, z = {row['zscore']:+g})")
    detail = " ".join(parts) or "no longer trips detection"
    return (
        f"**{row['entity']}** {row.get('metric') or 'activity'} {detail} "
        f"as of {row.get('as_of')}. _Numbers from the committed flags ledger._"
    )


# --- the run record, read from the freshly published artifacts ----------------


def _load_json(path: Path):
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return None


def _layer_freshness(data_dir: Path) -> dict[str, str | None]:
    """stem -> the sidecar's OWN ``as_of`` (else ``generated_at``, else null) for
    every published top-level ``*.json``. The per-layer freshness map the
    max-age work (H1-E) reads back; an array-shaped sidecar (flags) has no
    top-level stamp yet, recorded honestly as null."""
    out: dict[str, str | None] = {}
    for p in sorted(data_dir.glob("*.json")):
        if p.name == "manifest.json":
            continue
        d = _load_json(p)
        out[p.stem] = (d.get("as_of") or d.get("generated_at")) if isinstance(d, dict) else None
    return out


def build_run_record(data_dir: Path) -> dict:
    """One run_ledger line, read entirely from the published store at ``data_dir``."""
    snapshot = _load_json(data_dir / "snapshot.json") or {}
    manifest = _load_json(data_dir / "manifest.json") or {}
    stress = _load_json(data_dir / "stress.json") or {}
    flags = _load_json(data_dir / "flags.json")
    spine_as_of = snapshot.get("as_of") or manifest.get("as_of")
    if not spine_as_of:
        raise SystemExit(f"ledger: no spine as_of in {data_dir}/snapshot.json or manifest.json")
    flag_count = manifest.get("flag_count")
    if flag_count is None:
        flag_count = len(flags) if isinstance(flags, list) else 0
    return {
        "run_key": spine_as_of,
        "generated_at": manifest.get("generated_at") or snapshot.get("generated_at"),
        "manifest_version": manifest.get("version"),
        "spine_as_of": spine_as_of,
        "stress": {
            "index": stress.get("index"),
            "label": stress.get("label"),
            "as_of": stress.get("as_of"),
        },
        "flag_count": flag_count,
        "layers": _layer_freshness(data_dir),
    }


def record_run(data_dir: Path, state: Path | None = None) -> dict:
    """Append both ledgers for the published run at ``data_dir``. Idempotent."""
    st = state or state_dir()
    run = build_run_record(data_dir)
    flags = _load_json(data_dir / "flags.json")
    if not isinstance(flags, list):
        raise SystemExit(f"ledger: {data_dir}/flags.json missing or malformed")
    return {
        "run_key": run["run_key"],
        "new_flag_rows": append_flags(run["run_key"], flags, st, generated_at=run.get("generated_at")),
        "new_run": append_run(run, st),
        "flag_count": run["flag_count"],
        "state_dir": str(st),
    }


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(
        prog="python -m freight_radar.ledger",
        description="Append the committed run + flags ledgers from a published data dir.",
    )
    ap.add_argument("data_dir", help="published store, e.g. ../frontend/public/data")
    ap.add_argument("--state-dir", default=None, help="ledger dir (default: data/state/)")
    args = ap.parse_args(argv)
    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        raise SystemExit(f"ledger: published data dir not found: {data_dir}")
    r = record_run(data_dir, Path(args.state_dir) if args.state_dir else None)
    if r["new_run"] or r["new_flag_rows"]:
        print(
            f"ledger: recorded run {r['run_key']} — {r['new_flag_rows']} flag rows "
            f"+ {int(r['new_run'])} run row -> {r['state_dir']}"
        )
    else:  # idempotent re-run: already recorded, exit 0
        print(f"ledger: run {r['run_key']} already recorded — no-op ({r['state_dir']})")


if __name__ == "__main__":
    main()
