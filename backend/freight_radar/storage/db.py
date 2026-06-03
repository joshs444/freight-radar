"""DuckDB storage: connect, init schema, idempotent upserts, provenance."""

from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from ..config import DEFAULT_DB_PATH

_SCHEMA_SQL = Path(__file__).resolve().parent / "schema.sql"


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> duckdb.DuckDBPyConnection:
    """Open (creating parent dir if needed) and initialize the schema."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    init_schema(con)
    return con


def init_schema(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(_SCHEMA_SQL.read_text())


def upsert_df(con: duckdb.DuckDBPyConnection, table: str, df: pd.DataFrame) -> int:
    """INSERT OR REPLACE the frame into ``table`` keyed on its PRIMARY KEY.

    Idempotent: re-running a window overwrites the same (portid, date) rows.
    Column names in ``df`` must match the target columns; order is taken from df.
    """
    if df.empty:
        return 0
    cols = ", ".join(f'"{c}"' for c in df.columns)
    con.register("_upsert_src", df)
    try:
        con.execute(
            f"INSERT OR REPLACE INTO {table} ({cols}) SELECT {cols} FROM _upsert_src"
        )
    finally:
        con.unregister("_upsert_src")
    return len(df)


def record_ingest_run(
    con: duckdb.DuckDBPyConnection,
    *,
    run_id: str,
    kind: str,
    started_at: datetime,
    finished_at: datetime,
    rows_written: int,
    status: str = "ok",
    detail: str = "",
) -> None:
    con.execute(
        "INSERT INTO meta_ingest_runs "
        "(run_id, kind, started_at, finished_at, rows_written, status, detail) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        [run_id, kind, started_at, finished_at, rows_written, status, detail],
    )


def update_source_status(
    con: duckdb.DuckDBPyConnection,
    *,
    source: str,
    last_success: datetime,
    max_data_date: date | None,
    status: str = "ok",
    note: str = "",
) -> None:
    con.execute(
        "INSERT OR REPLACE INTO meta_source_status "
        "(source, last_success, max_data_date, status, note) VALUES (?, ?, ?, ?, ?)",
        [source, last_success, max_data_date, status, note],
    )


def join_coverage(
    con: duckdb.DuckDBPyConnection, fct_table: str, dim_table: str
) -> float:
    """Fraction of distinct fact portids that resolve to a dim row (lat/lon)."""
    row = con.execute(
        f"""
        WITH f AS (SELECT DISTINCT portid FROM {fct_table})
        SELECT
            COUNT(*) AS total,
            COUNT(d.portid) AS matched
        FROM f LEFT JOIN {dim_table} d USING (portid)
        """
    ).fetchone()
    total, matched = row[0], row[1]
    return (matched / total) if total else 0.0
