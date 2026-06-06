"""Python <-> dbt numeric parity — the Acceptance Harness's strongest correctness gate.

Two *independent* implementations of the Global Ocean Freight Stress Index must agree
to the last published digit:

  * Python   — narrative/stress.py compute() over export_timeseries' timeseries.json
  * dbt      — mart_freight_stress_index (int_chokepoint_stress -> blend), materialized
               by `dbt build` into the hermetic fixture warehouse

Both read the same fct_chokepoint_daily, so identical math => identical index. A drift in
either implementation (a refactor that changes a number, a dbt model that diverges from
the Python method) fails here. This runs in CI right after `dbt build`, where the marts
are materialized and the backend package is installed (the dbt-build job).

    cd backend && FREIGHT_RADAR_DB=... uv run python ../dbt/ci/check_parity.py

NOTE: only the stress index is a clean parity. mart_active_flags is a faithful
re-expression of the FROZEN fct_flags fixture (covered by dbt's own tests), whereas
Python *recomputes* flags from detection — different inputs, so not an equivalence.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

import duckdb

from freight_radar.export_timeseries import export_timeseries
from freight_radar.narrative.stress import compute

DB = os.environ.get("FREIGHT_RADAR_DB")
TOL = 0.1  # the index is published to one decimal; agreement must hold at that precision


def _fail(msg: str) -> None:
    print(f"\n  PARITY FAIL: {msg}")
    sys.exit(1)


def main() -> None:
    if not DB or not Path(DB).exists():
        _fail(f"FREIGHT_RADAR_DB not set or missing: {DB!r}")

    # --- Python side: the same path the app ships ---
    tmp = Path(tempfile.mkdtemp())
    export_timeseries(db_path=DB, out_dir=tmp)
    ts = json.loads((tmp / "timeseries.json").read_text())
    py = compute(ts)
    if not py.get("history"):
        _fail("Python compute() produced no history from the fixture timeseries")
    py_index = {d: round(float(v), 1) for d, v in zip(py["history_dates"], py["history"])}

    # --- dbt side: the materialized mart (schema-agnostic lookup) ---
    con = duckdb.connect(DB, read_only=True)
    schema = con.execute(
        "select table_schema from information_schema.tables "
        "where table_name = 'mart_freight_stress_index' limit 1"
    ).fetchone()
    if not schema:
        _fail("mart_freight_stress_index not found — did `dbt build` run first?")
    rows = con.execute(
        f"select cast(date as varchar), index_value, label "
        f"from {schema[0]}.mart_freight_stress_index order by date"
    ).fetchall()
    mart_index = {r[0]: round(float(r[1]), 1) for r in rows}
    mart_label = {r[0]: r[2] for r in rows}

    # --- compare: same coverage + same value every day ---
    py_only = sorted(set(py_index) - set(mart_index))
    mart_only = sorted(set(mart_index) - set(py_index))
    if py_only or mart_only:
        _fail(f"date coverage differs — python-only={py_only[:5]} dbt-only={mart_only[:5]}")

    mismatches = [
        (d, py_index[d], mart_index[d])
        for d in sorted(py_index)
        if abs(py_index[d] - mart_index[d]) > TOL
    ]
    if mismatches:
        for d, pv, mv in mismatches[:10]:
            print(f"    {d}: python={pv}  dbt={mv}")
        _fail(f"{len(mismatches)} of {len(py_index)} days differ in the stress index")

    # label parity on the current day (the headline the UI shows)
    last = sorted(py_index)[-1]
    if py["label"] != mart_label[last]:
        _fail(f"label differs on {last}: python={py['label']!r} dbt={mart_label[last]!r}")

    print(
        f"  PARITY OK — Python and dbt agree on the stress index across {len(py_index)} days "
        f"(current {last}: {py_index[last]} '{py['label']}')."
    )


if __name__ == "__main__":
    main()
