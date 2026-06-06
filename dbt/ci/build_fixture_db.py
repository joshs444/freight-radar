"""Build the hermetic CI warehouse (freight_radar_ci.duckdb) from committed CSVs.

CI runs this before `dbt build --target ci`. It creates the source tables with the
EXACT production DDL (backend/freight_radar/storage/schema.sql + detect/flags_schema.sql
— reused, never duplicated, so the fixture schema can't drift from prod) and loads the
small CSV slice in dbt/ci/fixtures/. No network, no 32 MB binary in git.

    cd backend && uv run python ../dbt/ci/build_fixture_db.py
writes ./freight_radar_ci.duckdb (honors FREIGHT_RADAR_DB if set).
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parents[1]
FIX = HERE / "fixtures"
PKG = REPO_ROOT / "backend" / "freight_radar"
SCHEMA_SQL = PKG / "storage" / "schema.sql"
FLAGS_SQL = PKG / "detect" / "flags_schema.sql"

# CSV file -> target table. Order is irrelevant (no FKs enforced on load).
FIXTURES = [
    "dim_chokepoint",
    "dim_port",
    "fct_chokepoint_daily",
    "fct_port_daily",
    "fct_flags",
    "meta_source_status",
]


def main() -> None:
    out = Path(os.environ.get("FREIGHT_RADAR_DB", str(HERE.parent / "freight_radar_ci.duckdb")))
    if out.exists():
        out.unlink()  # always rebuild clean
    con = duckdb.connect(str(out))

    # 1. Production DDL — identical schema to the real warehouse.
    con.execute(SCHEMA_SQL.read_text())
    con.execute(FLAGS_SQL.read_text())

    # 2. Load the committed CSV slice. read_csv infers types; INSERT BY NAME coerces
    #    into the DDL's typed columns (DATE strings -> DATE, etc.).
    for table in FIXTURES:
        csv = FIX / f"{table}.csv"
        con.execute(
            f"insert into {table} by name "
            f"select * from read_csv(?, header=true, dateformat='%Y-%m-%d')",
            [str(csv)],
        )
        n = con.execute(f"select count(*) from {table}").fetchone()[0]
        print(f"  loaded {table:24s} {n:>8,} rows")

    con.close()
    print(f"hermetic CI warehouse built -> {out}")


if __name__ == "__main__":
    main()
