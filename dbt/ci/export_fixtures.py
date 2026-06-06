"""Regenerate the hermetic CI fixtures from a real freight_radar.duckdb.

The production warehouse (data/freight_radar.duckdb, ~32 MB) is gitignored, so CI
can't run `dbt build` against it. Instead we commit a small, representative slice as
CSVs (this script writes them) and rebuild a tiny freight_radar_ci.duckdb from them
at job time (build_fixture_db.py). The slice is chosen so every model + test has real
data to chew on: all 28 chokepoints, the flagged ports plus the busiest ports, and
enough trailing history (DAYS) to cover the 120-day stress window + 28-day baseline.

Run manually when the schema or the desired sample changes:
    cd backend && uv run python ../dbt/ci/export_fixtures.py
(honors FREIGHT_RADAR_DB; defaults to ../data/freight_radar.duckdb).
"""

from __future__ import annotations

import os
from pathlib import Path

import duckdb

FIX = Path(__file__).resolve().parent / "fixtures"
DAYS = 160          # > 120 (stress window) + 28 (baseline) + margin
TOP_PORTS = 40      # busiest ports by fleet base, on top of every flagged port


def main() -> None:
    db = os.environ.get("FREIGHT_RADAR_DB", "../data/freight_radar.duckdb")
    con = duckdb.connect(db, read_only=True)
    FIX.mkdir(parents=True, exist_ok=True)

    max_choke = con.execute("select max(date) from fct_chokepoint_daily").fetchone()[0]
    max_port = con.execute("select max(date) from fct_port_daily").fetchone()[0]

    # Port universe: every flagged port + the TOP_PORTS busiest geo-carrying ports.
    port_ids = [r[0] for r in con.execute(
        f"""
        with flagged as (select distinct portid from fct_flags where portid like 'port%'),
        top as (select portid from dim_port where lat is not null
                order by vessel_count_total desc nulls last limit {TOP_PORTS})
        select portid from flagged union select portid from top
        """
    ).fetchall()]
    ph = ", ".join("?" for _ in port_ids)

    exports = {
        "dim_chokepoint": ("select * from dim_chokepoint order by portid", []),
        "dim_port": (f"select * from dim_port where portid in ({ph}) order by portid", port_ids),
        "fct_chokepoint_daily": (
            "select * from fct_chokepoint_daily where date > ?::date - ? order by portid, date",
            [max_choke, DAYS],
        ),
        "fct_port_daily": (
            f"select * from fct_port_daily where portid in ({ph}) and date > ?::date - ? order by portid, date",
            [*port_ids, max_port, DAYS],
        ),
        "fct_flags": ("select * from fct_flags order by flag_id", []),
        "meta_source_status": ("select * from meta_source_status order by source", []),
    }

    for table, (sql, params) in exports.items():
        out = FIX / f"{table}.csv"
        con.execute(f"copy ({sql}) to '{out}' (header, dateformat '%Y-%m-%d')", params)
        n = con.execute(f"select count(*) from ({sql})", params).fetchone()[0]
        kb = out.stat().st_size / 1024
        print(f"  {table:24s} {n:>8,} rows  {kb:7.1f} KB")

    con.close()
    print(f"fixtures written to {FIX} (ports in slice: {len(port_ids)})")


if __name__ == "__main__":
    main()
