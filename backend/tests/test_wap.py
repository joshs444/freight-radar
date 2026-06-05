"""Write-Audit-Publish seam — the receipt that the fact layer refuses bad data.

These tests prove the WAP contract end-to-end against a real (temp) DuckDB,
deterministically and with NO network:

  * a clean staged batch promotes atomically into the prod fact table, staging
    is emptied, and a deterministic lineage_run_id is recorded;
  * an error-severity DQ failure (all-NULL column, join-coverage shortfall) BLOCKS
    the promotion, RAISES, and leaves the prod fact table EXACTLY unchanged
    (atomicity — the swap never half-applies);
  * the DQ suite is enumerable (you can list the named checks + severities);
  * lineage_run_id is derived from the data (max date + row count), not the clock.

The checks reuse the existing guards' logic (join_coverage + MIN_JOIN_COVERAGE,
the all-NULL/column-drop assertion) rather than duplicating it.
"""

from __future__ import annotations

from datetime import date

import pytest

from freight_radar import wap
from freight_radar.config import MIN_JOIN_COVERAGE
from freight_radar.storage.db import connect


# --- fixtures ---------------------------------------------------------------
def _con(tmp_path):
    """A fresh schema'd DuckDB on disk (so transactions/rollback are real)."""
    return connect(tmp_path / "wap.duckdb")


def _seed_dim_chokepoint(con, portids):
    """One dim row per portid so the join-coverage check can resolve geometry."""
    for i, pid in enumerate(portids):
        con.execute(
            "INSERT OR REPLACE INTO dim_chokepoint (portid, lat, lon) VALUES (?, ?, ?)",
            [pid, 1.0 + i, 2.0 + i],
        )


def _stage_choke(con, rows):
    """rows: list of (portid, date_str, n_total). Other measures default to n_total."""
    for pid, d, n in rows:
        con.execute(
            "INSERT OR REPLACE INTO stg_chokepoint_daily "
            "(portid, date, portname, n_total, n_cargo) VALUES (?, ?, ?, ?, ?)",
            [pid, d, f"name_{pid}", n, n],
        )


# --- (c) the DQ suite is enumerable -----------------------------------------
def test_dq_suite_is_enumerable():
    checks = wap.list_checks()
    names = [c["name"] for c in checks]
    # the three promoted guards + the dup-key belt-and-suspenders, all named
    assert {"not_empty", "no_all_null_columns", "join_coverage"} <= set(names)
    # every check carries a warn/error severity
    assert all(c["severity"] in (wap.WARN, wap.ERROR) for c in checks)
    # join_coverage is an error-severity (publish-blocking) check
    assert next(c for c in checks if c["name"] == "join_coverage")["severity"] == wap.ERROR


# --- lineage id is deterministic + data-derived -----------------------------
def test_lineage_run_id_is_deterministic_from_the_data(tmp_path):
    con = _con(tmp_path)
    _stage_choke(con, [("chokepoint1", "2026-05-31", 10), ("chokepoint1", "2026-05-30", 9)])
    rid1 = wap.lineage_run_id(con, "stg_chokepoint_daily")
    rid2 = wap.lineage_run_id(con, "stg_chokepoint_daily")
    assert rid1 == rid2  # same data -> same id (not random / wall-clock)
    assert rid1 == "stg_chokepoint_daily-2026-05-31-r2"  # max date + row count
    con.execute("DELETE FROM stg_chokepoint_daily")
    assert wap.lineage_run_id(con, "stg_chokepoint_daily") == "stg_chokepoint_daily-empty"
    con.close()


# --- (a) clean staging promotes atomically ----------------------------------
def test_clean_staging_promotes_into_fact_and_empties_staging(tmp_path):
    con = _con(tmp_path)
    _seed_dim_chokepoint(con, ["chokepoint1", "chokepoint2"])
    _stage_choke(con, [
        ("chokepoint1", "2026-05-31", 10),
        ("chokepoint2", "2026-05-31", 20),
    ])

    result = wap.promote(con, "stg_chokepoint_daily")

    assert result["verdict"] == "pass"
    assert result["rows_promoted"] == 2
    assert result["lineage_run_id"] == "stg_chokepoint_daily-2026-05-31-r2"
    # rows are now LIVE in the prod fact table...
    fct = con.execute(
        "SELECT portid, n_total FROM fct_chokepoint_daily ORDER BY portid"
    ).fetchall()
    assert fct == [("chokepoint1", 10), ("chokepoint2", 20)]
    # ...and staging is emptied (never serves traffic between runs)
    assert con.execute("SELECT count(*) FROM stg_chokepoint_daily").fetchone()[0] == 0
    # lineage trail recorded
    lr = con.execute(
        "SELECT lineage_run_id, verdict, rows_promoted FROM meta_publish_runs"
    ).fetchone()
    assert lr == ("stg_chokepoint_daily-2026-05-31-r2", "pass", 2)
    con.close()


def test_promote_replaces_only_the_staged_keys_leaving_history(tmp_path):
    """The swap is a keyed replace, not a truncate: untouched history survives."""
    con = _con(tmp_path)
    _seed_dim_chokepoint(con, ["chokepoint1"])
    # prior published history for an OLD date
    con.execute(
        "INSERT INTO fct_chokepoint_daily (portid, date, n_total) VALUES ('chokepoint1', DATE '2026-01-01', 5)"
    )
    # a fresh pull revises a NEW date only
    _stage_choke(con, [("chokepoint1", "2026-05-31", 99)])
    wap.promote(con, "stg_chokepoint_daily")

    rows = con.execute(
        "SELECT date, n_total FROM fct_chokepoint_daily ORDER BY date"
    ).fetchall()
    assert rows == [(date(2026, 1, 1), 5), (date(2026, 5, 31), 99)]  # old kept, new added
    con.close()


# --- (b) an error-severity DQ failure BLOCKS + leaves prod unchanged --------
def test_join_coverage_shortfall_blocks_publish_and_is_atomic(tmp_path):
    con = _con(tmp_path)
    # dim covers chokepoint1 ONLY; staging includes an UNRESOLVABLE portid, so
    # join coverage = 1/2 = 0.5 < MIN_JOIN_COVERAGE -> error -> blocked.
    _seed_dim_chokepoint(con, ["chokepoint1"])
    # seed a known-good prod fact row that must be left UNTOUCHED on a blocked run
    con.execute(
        "INSERT INTO fct_chokepoint_daily (portid, date, n_total) VALUES ('chokepoint1', DATE '2026-01-01', 7)"
    )
    before = con.execute("SELECT portid, date, n_total FROM fct_chokepoint_daily").fetchall()

    _stage_choke(con, [
        ("chokepoint1", "2026-05-31", 10),
        ("ghost_port", "2026-05-31", 20),  # no dim row -> drags coverage to 0.5
    ])
    assert wap.join_coverage(con, "stg_chokepoint_daily", "dim_chokepoint") < MIN_JOIN_COVERAGE

    with pytest.raises(wap.PublishBlocked) as ei:
        wap.promote(con, "stg_chokepoint_daily")
    assert "join coverage" in str(ei.value)

    # prod fact table is EXACTLY as it was — the swap never half-applied
    after = con.execute("SELECT portid, date, n_total FROM fct_chokepoint_daily").fetchall()
    assert after == before == [("chokepoint1", date(2026, 1, 1), 7)]
    # staging is left intact (NOT emptied) so a blocked batch is inspectable
    assert con.execute("SELECT count(*) FROM stg_chokepoint_daily").fetchone()[0] == 2
    # the failed audit is still recorded in the lineage trail (verdict=fail, 0 rows)
    fail = con.execute(
        "SELECT verdict, rows_promoted FROM meta_publish_runs WHERE verdict='fail'"
    ).fetchone()
    assert fail == ("fail", 0)
    con.close()


def test_all_null_measure_column_blocks_publish_and_is_atomic(tmp_path):
    con = _con(tmp_path)
    _seed_dim_chokepoint(con, ["chokepoint1"])
    con.execute(
        "INSERT INTO fct_chokepoint_daily (portid, date, n_total) VALUES ('chokepoint1', DATE '2026-01-01', 7)"
    )
    before = con.execute("SELECT * FROM fct_chokepoint_daily").fetchall()
    # stage rows whose required measure column (n_total) is entirely NULL — the
    # all-NULL/column-drop failure mode, now caught at the DB level pre-swap.
    con.execute(
        "INSERT INTO stg_chokepoint_daily (portid, date, n_total) VALUES ('chokepoint1', DATE '2026-05-31', NULL)"
    )

    report = wap.audit(con, "stg_chokepoint_daily")
    assert not report.passed
    assert any(r.name == "no_all_null_columns" and not r.ok for r in report.results)

    with pytest.raises(wap.PublishBlocked):
        wap.promote(con, "stg_chokepoint_daily")
    assert con.execute("SELECT * FROM fct_chokepoint_daily").fetchall() == before
    con.close()


def test_empty_staging_blocks_publish(tmp_path):
    """Nothing staged is an error: a publish with zero rows would blank the layer."""
    con = _con(tmp_path)
    _seed_dim_chokepoint(con, ["chokepoint1"])
    report = wap.audit(con, "stg_chokepoint_daily")
    assert not report.passed
    with pytest.raises(wap.PublishBlocked):
        wap.promote(con, "stg_chokepoint_daily")
    con.close()


def test_audit_report_serializes_and_lists_failures(tmp_path):
    con = _con(tmp_path)
    _seed_dim_chokepoint(con, ["chokepoint1"])
    _stage_choke(con, [("chokepoint1", "2026-05-31", 10)])
    report = wap.audit(con, "stg_chokepoint_daily")
    d = report.as_dict()
    assert d["verdict"] == "pass" and d["stg"] == "stg_chokepoint_daily"
    assert {c["name"] for c in d["checks"]} >= {"not_empty", "join_coverage"}
    assert report.failures() == []  # clean batch has no error-severity failures
    con.close()
