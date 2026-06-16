"""F1 — the committed JSONL ledgers (ADR-0009): unit + the continuity receipt.

Three layers, all hermetic (every test injects a tmp state dir — the autouse
guard in conftest.py additionally fences off the real ``data/state/``):

  * unit: append/dedup/atomicity/read-back for ``flags_ledger.jsonl`` +
    ``run_ledger.jsonl``, including the slim-row contract (no prose fields) and
    the prior-row widening lifecycle.py consumes;
  * the CLI (``python -m freight_radar.ledger <published_dir>``): records both
    ledgers from real published artifacts, and a re-run is a byte-stable no-op
    that still exits 0 (refresh.yml can re-fire it safely);
  * THE RECEIPT: two full detection runs over fixture spine data where the
    second starts from a FRESH DuckDB but the same state dir — the exact
    production situation the old ``fct_flags`` read-back failed (weekly rebuild
    -> empty table -> every flag forever "new"). With the ledger as the only
    prior-flags source, run 2 carries ``ongoing`` continuity and a flag absent
    in run 2 ships a ``resolved`` tombstone.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import pytest

from freight_radar import ledger
from freight_radar.detect.run_detection import _load_prior_flags, run

RUN1, RUN2 = "2026-02-25", "2026-03-04"


def _flag(fid: str = "f1", **over) -> dict:
    """A published-shaped flag dict (the superset flags.json carries)."""
    base = {
        "flag_id": fid, "kind": "chokepoint_transit_collapse", "portid": "cp1",
        "entity": "Alpha Strait", "lat": 10.0, "lon": 20.0, "severity": 50,
        "lifecycle": "new", "zscore": -4.2, "value": 12.0, "baseline": 30.0,
        "pct_change": -60.0, "metric": "n_total", "as_of": "2026-03-02",
        "headline": "Alpha Strait transit 60% below its 28-day norm",
        # bulk/static fields the ledger must slim off:
        "brief_md": "**Alpha Strait** transit fell ... (a long markdown brief)",
        "source": "IMF PortWatch", "source_url": "https://example", "license": "x",
        "method": "STL(7,robust) residual + 28d rolling z",
    }
    base.update(over)
    return base


# --- unit: append / dedup / read-back ----------------------------------------


def test_append_flags_slim_rows_and_prior_widening(tmp_path: Path):
    assert ledger.append_flags(RUN1, [_flag()], tmp_path) == 1
    rows = ledger.read_flags(tmp_path)
    assert len(rows) == 1
    row = rows[0]
    assert set(row) == {"run_key", "generated_at", *ledger.FLAG_FIELDS}, \
        "slim line only — identity + numbers + the run discriminator, no prose/static fields"
    assert "brief_md" not in row and "source" not in row
    assert row["run_key"] == RUN1 and row["severity"] == 50

    prior = ledger.prior_flags(tmp_path)
    assert set(prior) == {"f1"}
    p = prior["f1"]
    # everything lifecycle.py touches is present; brief_md is rebuilt from the numbers
    for k in ("flag_id", "kind", "entity", "portid", "lat", "lon", "severity",
              "headline", "brief_md", "metric", "value", "baseline", "pct_change",
              "zscore", "as_of", "lifecycle"):
        assert k in p, k
    assert "Alpha Strait" in p["brief_md"] and "12" in p["brief_md"]

    # the run_detection seam reads the same dict through the parameterized state dir
    assert _load_prior_flags(tmp_path) == prior


def test_append_is_idempotent_and_byte_stable(tmp_path: Path):
    flags = [_flag("a1"), _flag("a2", portid="cp2", entity="Beta Canal")]
    assert ledger.append_flags(RUN1, flags, tmp_path) == 2
    path = tmp_path / ledger.FLAGS_LEDGER
    before = path.read_bytes()
    assert ledger.append_flags(RUN1, flags, tmp_path) == 0, "same (run_key, flag_id) -> no-op"
    assert path.read_bytes() == before, "re-append must be byte-stable"
    # a new flag for the same run lands; the existing pair still dedups
    assert ledger.append_flags(RUN1, [_flag("a1"), _flag("a3", portid="cp3")], tmp_path) == 1
    assert len(ledger.read_flags(tmp_path)) == 3
    assert not list(tmp_path.glob("*.tmp")), "atomic rename leaves no temp litter"


def test_append_run_dedups_on_run_and_picks_latest_by_recording_order(tmp_path: Path):
    rec = {"run_key": RUN1, "generated_at": "2026-02-25T08:00:00+00:00", "flag_count": 2}
    assert ledger.append_run(rec, tmp_path) is True
    assert ledger.append_run(rec, tmp_path) is False, "same (run_key, generated_at) -> no-op"
    # a re-detection on the SAME spine date but a new publish is a DIFFERENT run
    rec2 = {**rec, "generated_at": "2026-02-25T15:00:00+00:00", "flag_count": 3}
    assert ledger.append_run(rec2, tmp_path) is True, "same run_key, new generated_at -> recorded"
    assert ledger.append_run({**rec, "run_key": RUN2}, tmp_path) is True
    # a later run whose spine as_of REGRESSED (partial upstream fetch) is still 'latest'
    assert ledger.append_run(
        {"run_key": "2026-02-18", "generated_at": "z", "flag_count": 0}, tmp_path
    ) is True
    assert ledger.latest_run_key(tmp_path) == "2026-02-18", "latest = last recorded, not max(run_key)"
    assert ledger.latest_run(tmp_path)["flag_count"] == 0


def test_same_spine_rerun_records_revised_flag_state(tmp_path: Path):
    """The production norm: two refreshes land on the SAME spine ``as_of`` (run_key)
    because the PortWatch date lags and repeats, but a revised in-window fetch
    re-detects the same flag_id with new numbers. The second run must NOT be
    silently dropped against the first run's stale row, and prior_flags must seed
    lifecycle from the NEWER run — the continuity the ledger exists to deliver."""
    gen_a, gen_b = "2026-03-04T08:00:00+00:00", "2026-03-04T16:30:00+00:00"
    assert ledger.append_flags(RUN2, [_flag("f1", severity=50)], tmp_path, generated_at=gen_a) == 1
    # same run_key + flag_id, escalated severity, NEW publish -> a genuinely new run
    assert ledger.append_flags(
        RUN2, [_flag("f1", severity=80, lifecycle="ongoing")], tmp_path, generated_at=gen_b
    ) == 1, "a revised re-detection on the same spine date must record, not no-op"
    # but re-firing the SECOND run against the same published dir is still byte-stable
    before = (tmp_path / ledger.FLAGS_LEDGER).read_bytes()
    assert ledger.append_flags(
        RUN2, [_flag("f1", severity=80, lifecycle="ongoing")], tmp_path, generated_at=gen_b
    ) == 0
    assert (tmp_path / ledger.FLAGS_LEDGER).read_bytes() == before
    # prior_flags seeds from the LATEST run (gen_b), never the frozen first row
    ledger.append_run({"run_key": RUN2, "generated_at": gen_a}, tmp_path)
    ledger.append_run({"run_key": RUN2, "generated_at": gen_b}, tmp_path)
    assert ledger.prior_flags(tmp_path)["f1"]["severity"] == 80, \
        "lifecycle must seed from the revised run, not the stale same-run_key row"


def test_prior_flags_latest_run_only_excluding_resolved(tmp_path: Path):
    ledger.append_flags(RUN1, [_flag("f1", severity=50), _flag("f2", portid="cp2")], tmp_path)
    ledger.append_flags(
        RUN2,
        [_flag("f1", severity=64, lifecycle="ongoing"),
         _flag("f2", portid="cp2", lifecycle="resolved")],
        tmp_path,
    )
    prior = ledger.prior_flags(tmp_path)
    assert set(prior) == {"f1"}, "run-2's resolved tombstone must not re-resolve forever"
    assert prior["f1"]["severity"] == 64, "rows must come from the LATEST run, not run 1"
    # a recorded run with zero active flags means: nothing prior (all clear)
    ledger.append_run({"run_key": "2026-03-11", "flag_count": 0}, tmp_path)
    assert ledger.prior_flags(tmp_path) == {}


def test_empty_state_and_torn_lines(tmp_path: Path):
    assert ledger.prior_flags(tmp_path) == {}
    assert ledger.latest_run_key(tmp_path) is None
    # a torn trailing line (crashed non-atomic writer) is skipped, not fatal
    path = tmp_path / ledger.FLAGS_LEDGER
    good = json.dumps({"run_key": RUN1, "flag_id": "ok1", "kind": "k", "portid": "p"})
    path.write_text(good + '\n{"run_key": "2026-03-0')
    assert [r["flag_id"] for r in ledger.read_flags(tmp_path)] == ["ok1"]
    assert ledger.append_flags(RUN1, [_flag("ok2")], tmp_path) == 1


# --- the CLI against a published store ---------------------------------------


def _published_dir(out: Path, as_of: str, flags: list[dict] | None = None) -> Path:
    """Stamp the minimal published store the ledger CLI reads (flags.json may
    already be there, written by the detector itself)."""
    out.mkdir(exist_ok=True)
    if flags is not None:
        (out / "flags.json").write_text(json.dumps(flags, indent=2))
    n_flags = len(json.loads((out / "flags.json").read_text()))
    (out / "snapshot.json").write_text(json.dumps(
        {"as_of": as_of, "generated_at": f"{as_of}T08:00:00+00:00"}))
    (out / "manifest.json").write_text(json.dumps(
        {"version": 9, "as_of": as_of, "generated_at": f"{as_of}T08:21:00+00:00",
         "flag_count": n_flags}))
    (out / "stress.json").write_text(json.dumps(
        {"index": 41.6, "label": "high", "as_of": as_of, "generated_at": as_of}))
    (out / "quakes.json").write_text(json.dumps({"generated_at": as_of, "items": []}))
    return out


def test_cli_records_then_reruns_byte_stable(tmp_path: Path, capsys):
    out = _published_dir(tmp_path / "pub", RUN2, [_flag("c1"), _flag("c2", portid="cp2")])
    state = tmp_path / "state"

    ledger.main([str(out), "--state-dir", str(state)])
    assert f"recorded run {RUN2}" in capsys.readouterr().out
    runs = ledger.read_runs(state)
    assert len(runs) == 1
    rec = runs[0]
    assert rec["run_key"] == RUN2 == rec["spine_as_of"]
    assert rec["manifest_version"] == 9 and rec["flag_count"] == 2
    assert rec["stress"] == {"index": 41.6, "label": "high", "as_of": RUN2}
    # per-layer freshness: every sidecar's own stamp; the (array-shaped) flags is null
    assert rec["layers"] == {"flags": None, "quakes": RUN2, "snapshot": RUN2, "stress": RUN2}
    assert len(ledger.read_flags(state)) == 2

    flags_before = (state / ledger.FLAGS_LEDGER).read_bytes()
    runs_before = (state / ledger.RUN_LEDGER).read_bytes()
    ledger.main([str(out), "--state-dir", str(state)])  # idempotent re-run: exit 0
    assert "already recorded" in capsys.readouterr().out
    assert (state / ledger.FLAGS_LEDGER).read_bytes() == flags_before
    assert (state / ledger.RUN_LEDGER).read_bytes() == runs_before


def test_cli_fails_loud_without_a_spine(tmp_path: Path):
    empty = tmp_path / "pub"
    empty.mkdir()
    with pytest.raises(SystemExit):
        ledger.main([str(empty), "--state-dir", str(tmp_path / "state")])
    with pytest.raises(SystemExit):
        ledger.main([str(tmp_path / "nope"), "--state-dir", str(tmp_path / "state")])


# --- THE RECEIPT: lifecycle continuity across two fresh-DB detection runs ----

CHOKEPOINT_NAMES = {"cpA": "Alpha Strait", "cpB": "Beta Canal"}


def _collapse() -> np.ndarray:
    """57 flat days then a sustained 6-day step down — the proven level-shift
    recipe from test_detection_depth (fires chokepoint_transit_collapse)."""
    rng = np.random.default_rng(7)
    return np.concatenate([29 + rng.normal(0, 0.6, 57), 16 + rng.normal(0, 0.4, 6)])


def _calm() -> np.ndarray:
    rng = np.random.default_rng(3)
    return 30 + rng.normal(0, 0.6, 63)


def _spine_db(db_path: Path, series_by_port: dict[str, np.ndarray]) -> None:
    """A from-scratch DuckDB with exactly the spine tables run() reads — built
    fresh per run, like the weekly refresh rebuilds the real warehouse."""
    dates = pd.date_range("2026-01-01", periods=63, freq="D")
    dims = pd.DataFrame([
        {"portid": pid, "fullname": CHOKEPOINT_NAMES[pid], "lat": 10.0 + i,
         "lon": 20.0 + i, "vessel_count_total": 9000 - 1000 * i}
        for i, pid in enumerate(series_by_port)
    ])
    daily = pd.DataFrame([
        {"portid": pid, "date": d.date(), "n_total": float(v),
         "capacity_total": float(v) * 25000.0}
        for pid, vals in series_by_port.items()
        for d, v in zip(dates, vals)
    ])
    con = duckdb.connect(str(db_path))
    try:
        con.register("_dims", dims)
        con.register("_daily", daily)
        con.execute("CREATE TABLE dim_chokepoint AS SELECT * FROM _dims")
        con.execute("CREATE TABLE fct_chokepoint_daily AS SELECT * FROM _daily")
        # the port tables exist but are empty — this receipt is about continuity
        con.execute(
            "CREATE TABLE dim_port (portid VARCHAR, portname VARCHAR, fullname VARCHAR,"
            " country VARCHAR, lat DOUBLE, lon DOUBLE, vessel_count_total DOUBLE,"
            " share_country_maritime_import DOUBLE, share_country_maritime_export DOUBLE)"
        )
        con.execute(
            "CREATE TABLE fct_port_daily (portid VARCHAR, date DATE, portcalls_total DOUBLE,"
            " portcalls_container DOUBLE, portcalls_tanker DOUBLE, portcalls_dry_bulk DOUBLE,"
            " portcalls_general_cargo DOUBLE, portcalls_roro DOUBLE)"
        )
    finally:
        con.close()


def test_lifecycle_survives_a_fresh_db_rebuild(tmp_path: Path, monkeypatch):
    """Run 1 detects two collapses (all "new"), the refresh-step CLI records the
    ledger, run 2 starts from a brand-new DuckDB + the same state dir: the
    continuing anomaly is "ongoing" (not "new" again) and the cleared one ships
    a one-shot "resolved" tombstone — the H1-A fix, end to end."""
    state = tmp_path / "state"
    monkeypatch.setenv("FREIGHT_RADAR_STATE_DIR", str(state))

    # --- run 1: both chokepoints collapsed; ledger is empty -> everything "new"
    db1 = tmp_path / "run1.duckdb"
    _spine_db(db1, {"cpA": _collapse(), "cpB": _collapse()})
    out1 = tmp_path / "pub"
    out1.mkdir()
    flags1 = run(db_path=db1, flags_json=out1 / "flags.json")
    by_port1 = {f.portid: f for f in flags1}
    assert set(by_port1) == {"cpA", "cpB"}
    assert all(f.lifecycle == "new" for f in flags1), "empty ledger -> honest baseline"

    # the refresh.yml ledger step, against the freshly published artifacts
    _published_dir(out1, "2026-03-04")
    ledger.main([str(out1), "--state-dir", str(state)])
    assert len(ledger.read_flags(state)) == 2

    # --- run 2: a FRESH warehouse (the weekly rebuild). cpA still collapsed,
    # cpB recovered. Without the ledger, prior state would be {} again.
    db2 = tmp_path / "run2.duckdb"
    _spine_db(db2, {"cpA": _collapse(), "cpB": _calm()})
    flags2 = run(db_path=db2, flags_json=tmp_path / "flags2.json")
    by_port2 = {f.portid: f for f in flags2}

    assert set(by_port2) == {"cpA", "cpB"}
    lifecycles = {pid: f.lifecycle for pid, f in by_port2.items()}
    assert lifecycles["cpA"] == "ongoing", (
        f"continuity across the rebuild must survive via the ledger, got {lifecycles}"
    )
    assert lifecycles["cpB"] == "resolved", "a cleared flag ships a tombstone"
    assert any(f.lifecycle != "new" for f in flags2), "not all 'new' — the critical fix"

    tomb = by_port2["cpB"]
    assert tomb.severity == int(round(by_port1["cpB"].severity * 0.5)), "decayed once"
    assert tomb.headline.startswith("[Resolved]")
    assert tomb.entity == "Beta Canal" and (tomb.lat, tomb.lon) == (11.0, 21.0)
    assert "_Resolved:" in tomb.brief_md

    # the published artifact carries the continuity too
    published = json.loads((tmp_path / "flags2.json").read_text())
    assert {f["portid"]: f["lifecycle"] for f in published} == lifecycles
