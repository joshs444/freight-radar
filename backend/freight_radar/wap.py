"""Write-Audit-Publish (WAP) — the Netflix-origin pattern for the fact layer.

Before this seam, the ETL guards fired AFTER rows were already live in the
``fct_*`` tables: ingest upserted, *then* checked coverage — so a bad pull was
visible to the app for the moment between the write and the gate. WAP closes
that gap on the ingest side (publish was already atomic):

  Write   land each fresh PortWatch pull into ``stg_*`` staging tables.
  Audit   run an enumerable data-quality suite (the three existing fail-loud
          guards, promoted into named pass/fail checks) against STAGING.
  Publish only on a clean audit, atomically swap staging -> prod ``fct_*``
          inside one DuckDB transaction. Any error-severity failure RAISES and
          the prod fact table is left UNCHANGED — the pipeline refuses to
          publish bad data.

The DQ suite is a *registry* (``CHECKS``): a list of named checks, each a small
function returning a ``CheckResult`` with a warn/error severity. New checks are
one append; ``list_checks()`` enumerates them for ops/tests.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Callable

import duckdb

from ._log import get_logger
from .config import MIN_JOIN_COVERAGE
from .storage.db import join_coverage

log = get_logger(__name__)

# severities: an ``error`` blocks the publish (raises); a ``warn`` is logged but
# does not block (a soft signal the data drifted, still publishable).
ERROR = "error"
WARN = "warn"

# staged table -> (prod fact table, dim table for the join-coverage check)
_PAIRS = {
    "stg_chokepoint_daily": ("fct_chokepoint_daily", "dim_chokepoint"),
    "stg_port_daily": ("fct_port_daily", "dim_port"),
}

# columns that must never be entirely NULL in staging (a silent all-NULL column
# is the schema-drift failure the ingest ``_to_frame`` guard catches at parse
# time; this is the same assertion re-checked at the DB level, post-write).
_NOT_ALL_NULL = {
    "stg_chokepoint_daily": ("portid", "date", "n_total"),
    "stg_port_daily": ("portid", "date", "portcalls_total"),
}


# --- result + check types ---------------------------------------------------
@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    severity: str          # WARN | ERROR
    message: str

    def as_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "severity": self.severity, "message": self.message}


@dataclass(frozen=True)
class Check:
    """A named data-quality check over one staged table."""
    name: str
    severity: str
    fn: Callable[[duckdb.DuckDBPyConnection, str], CheckResult]


# --- the checks (reuse the existing guards' logic, don't duplicate it) ------
def _check_not_empty(con: duckdb.DuckDBPyConnection, stg: str) -> CheckResult:
    n = con.execute(f"SELECT count(*) FROM {stg}").fetchone()[0]
    return CheckResult(
        "not_empty", n > 0, ERROR,
        f"{stg}: {n} staged rows" if n else f"{stg}: staging is EMPTY — nothing to publish",
    )


def _check_no_all_null_columns(con: duckdb.DuckDBPyConnection, stg: str) -> CheckResult:
    """Same intent as the ingest column-drop guard: a wholly-NULL key/measure
    column means upstream renamed/dropped a field and it landed all-NULL."""
    if con.execute(f"SELECT count(*) FROM {stg}").fetchone()[0] == 0:
        return CheckResult("no_all_null_columns", True, ERROR, f"{stg}: empty, no columns to check")
    bad: list[str] = []
    for col in _NOT_ALL_NULL[stg]:
        non_null = con.execute(f'SELECT count("{col}") FROM {stg}').fetchone()[0]
        if non_null == 0:
            bad.append(col)
    return CheckResult(
        "no_all_null_columns", not bad, ERROR,
        f"{stg}: columns all-NULL {bad} — upstream schema drift" if bad
        else f"{stg}: no all-NULL key/measure columns",
    )


def _check_join_coverage(con: duckdb.DuckDBPyConnection, stg: str) -> CheckResult:
    """Same gate as ``activities._assert_join_coverage`` / ``backfill``: the
    staged portids must resolve to a dim row (lat/lon) at >= MIN_JOIN_COVERAGE,
    or the published map would be half-empty. Run against STAGING so the break
    is caught before the swap, not after."""
    _, dim = _PAIRS[stg]
    cov = join_coverage(con, stg, dim)
    return CheckResult(
        "join_coverage", cov >= MIN_JOIN_COVERAGE, ERROR,
        f"{stg}->{dim} join coverage {cov:.3f} "
        f"({'>=' if cov >= MIN_JOIN_COVERAGE else '<'} {MIN_JOIN_COVERAGE})",
    )


def _check_no_duplicate_keys(con: duckdb.DuckDBPyConnection, stg: str) -> CheckResult:
    """(portid, date) is the prod PK; a duplicate in staging would mean the
    upstream window doubled a row. The PK on stg_* already rejects this on
    insert, so this is a belt-and-suspenders read-side assertion."""
    dups = con.execute(
        f"SELECT count(*) FROM (SELECT portid, date FROM {stg} GROUP BY 1,2 HAVING count(*) > 1)"
    ).fetchone()[0]
    return CheckResult(
        "no_duplicate_keys", dups == 0, WARN,
        f"{stg}: {dups} duplicate (portid,date) keys" if dups
        else f"{stg}: keys unique",
    )


# THE REGISTRY — enumerable; new checks are one append. ``list_checks`` reads it.
CHECKS: list[Check] = [
    Check("not_empty", ERROR, _check_not_empty),
    Check("no_all_null_columns", ERROR, _check_no_all_null_columns),
    Check("join_coverage", ERROR, _check_join_coverage),
    Check("no_duplicate_keys", WARN, _check_no_duplicate_keys),
]


def list_checks() -> list[dict]:
    """Enumerate the DQ suite (name + severity) without touching any data."""
    return [{"name": c.name, "severity": c.severity} for c in CHECKS]


# --- audit ------------------------------------------------------------------
@dataclass(frozen=True)
class AuditReport:
    stg: str
    results: list[CheckResult]

    @property
    def passed(self) -> bool:
        """An error-severity failure fails the audit; warns don't block."""
        return not any((not r.ok) and r.severity == ERROR for r in self.results)

    @property
    def verdict(self) -> str:
        return "pass" if self.passed else "fail"

    def failures(self) -> list[CheckResult]:
        return [r for r in self.results if not r.ok and r.severity == ERROR]

    def as_dict(self) -> dict:
        return {
            "stg": self.stg,
            "verdict": self.verdict,
            "checks": [r.as_dict() for r in self.results],
        }


def audit(con: duckdb.DuckDBPyConnection, stg: str) -> AuditReport:
    """Run every check in ``CHECKS`` against one staged table."""
    if stg not in _PAIRS:
        raise ValueError(f"unknown staging table {stg!r}; known: {sorted(_PAIRS)}")
    results = [c.fn(con, stg) for c in CHECKS]
    for r in results:
        lvl = log.error if (not r.ok and r.severity == ERROR) else (
            log.warning if not r.ok else log.debug
        )
        lvl("DQ[%s] %s: %s", stg, r.name, r.message)
    return AuditReport(stg, results)


# --- lineage ----------------------------------------------------------------
def lineage_run_id(con: duckdb.DuckDBPyConnection, stg: str) -> str:
    """Deterministic id for a staged batch: ``<table>-<max_date>-r<rows>``.

    Derived from the data itself (max date + row count), NOT wall-clock / random,
    so the same data re-published yields the same id and a published map is
    traceable back to the batch that produced it. Empty staging -> ``<table>-empty``.
    """
    row = con.execute(f"SELECT max(date), count(*) FROM {stg}").fetchone()
    max_date, n = row[0], row[1]
    if not n:
        return f"{stg}-empty"
    return f"{stg}-{max_date.isoformat()}-r{n}"


# --- publish (atomic swap) --------------------------------------------------
class PublishBlocked(RuntimeError):
    """An error-severity DQ failure blocked the staging->fact promotion."""


def promote(con: duckdb.DuckDBPyConnection, stg: str) -> dict:
    """Audit ``stg`` and, only on a clean verdict, atomically swap it into prod.

    The swap is one DuckDB transaction: DELETE the staged keys from the fact
    table, INSERT the staged rows, then TRUNCATE staging. If ANY step (or the
    audit) fails, the transaction rolls back and the prod fact table is left
    EXACTLY as it was — atomicity. An error-severity audit failure raises
    ``PublishBlocked`` and never opens the transaction at all.

    Returns the lineage record (also written to ``meta_publish_runs``).
    """
    fct, _ = _PAIRS[stg]
    report = audit(con, stg)
    run_id = lineage_run_id(con, stg)

    if not report.passed:
        msgs = "; ".join(r.message for r in report.failures())
        _record_publish_run(con, run_id, report, rows=0)
        raise PublishBlocked(
            f"{stg}: DQ audit FAILED, refusing to publish to {fct} — {msgs}"
        )

    rows = con.execute(f"SELECT count(*) FROM {stg}").fetchone()[0]
    con.execute("BEGIN TRANSACTION")
    try:
        # swap: replace exactly the staged (portid, date) keys, leave the rest of
        # the fact history untouched. INSERT...SELECT keeps it in-DB (no round-trip).
        con.execute(
            f"DELETE FROM {fct} WHERE (portid, date) IN (SELECT portid, date FROM {stg})"
        )
        con.execute(f"INSERT INTO {fct} SELECT * FROM {stg}")
        con.execute(f"DELETE FROM {stg}")  # staging is empty between runs
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise

    _record_publish_run(con, run_id, report, rows=rows)
    log.info("WAP publish: %s -> %s promoted %s rows (run_id=%s)", stg, fct, rows, run_id)
    return {
        "lineage_run_id": run_id,
        "stg": stg,
        "fct": fct,
        "verdict": report.verdict,
        "rows_promoted": rows,
        "checks": [r.as_dict() for r in report.results],
    }


def _record_publish_run(
    con: duckdb.DuckDBPyConnection, run_id: str, report: AuditReport, *, rows: int
) -> None:
    con.execute(
        "INSERT INTO meta_publish_runs "
        "(lineage_run_id, promoted_at, verdict, checks_run, rows_promoted, detail) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        [
            run_id,
            datetime.now(),
            report.verdict,
            len(report.results),
            rows,
            json.dumps([r.as_dict() for r in report.results]),
        ],
    )
