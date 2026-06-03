"""Backfill / refresh the DuckDB backbone from PortWatch.

    python -m freight_radar.backfill                 # 180d backfill -> data/freight_radar.duckdb
    python -m freight_radar.backfill --days 30       # shorter window
    python -m freight_radar.backfill --incremental   # trailing-14d re-pull (revisable values)
    python -m freight_radar.backfill --no-ports      # chokepoints only (fast)

Idempotent: every fact row is keyed (portid, date) and INSERT OR REPLACE'd, so
re-running any window simply refreshes those rows.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from datetime import date, datetime, timedelta

from .arcgis import ArcGISClient
from .config import (
    BACKFILL_DAYS,
    DEFAULT_DB_PATH,
    INCREMENTAL_REPULL_DAYS,
    MIN_JOIN_COVERAGE,
)
from .ingest.dims import load_dims
from .ingest.portwatch import load_chokepoint_daily, load_port_daily
from .storage.db import (
    connect,
    join_coverage,
    record_ingest_run,
    update_source_status,
)


async def run_backfill(
    *, db_path=DEFAULT_DB_PATH, days: int = BACKFILL_DAYS, with_ports: bool = True
) -> dict:
    con = connect(db_path)
    end = date.today()
    start = end - timedelta(days=days)
    run_id = f"{datetime.now():%Y%m%dT%H%M%S}-{uuid.uuid4().hex[:8]}"
    t0 = datetime.now()

    async with ArcGISClient() as client:
        dim_counts = await load_dims(con, client)
        print(f"  dims: {dim_counts}")

        choke_rows = await load_chokepoint_daily(con, client, start, end)
        print(f"  fct_chokepoint_daily: +{choke_rows} rows")

        port_rows = 0
        if with_ports:
            port_rows = await load_port_daily(con, client, start, end)
            print(f"  fct_port_daily: +{port_rows} rows")

    # --- receipts -----------------------------------------------------------
    choke_max = con.execute("SELECT max(date) FROM fct_chokepoint_daily").fetchone()[0]
    port_max = con.execute("SELECT max(date) FROM fct_port_daily").fetchone()[0]
    choke_cov = join_coverage(con, "fct_chokepoint_daily", "dim_chokepoint")
    port_cov = (
        join_coverage(con, "fct_port_daily", "dim_port") if with_ports else None
    )
    max_data_date = max(d for d in (choke_max, port_max) if d is not None)

    t1 = datetime.now()
    total_rows = sum(dim_counts.values()) + choke_rows + port_rows
    record_ingest_run(
        con,
        run_id=run_id,
        kind="backfill",
        started_at=t0,
        finished_at=t1,
        rows_written=total_rows,
        detail=f"days={days} ports={with_ports}",
    )
    update_source_status(
        con,
        source="portwatch",
        last_success=t1,
        max_data_date=max_data_date,
        status="ok",
        note=f"backfill {days}d; choke_cov={choke_cov:.3f} port_cov={port_cov}",
    )
    con.close()

    summary = {
        "run_id": run_id,
        "elapsed_s": round((t1 - t0).total_seconds(), 1),
        "window": [start.isoformat(), end.isoformat()],
        "chokepoint_rows": choke_rows,
        "port_rows": port_rows,
        "chokepoint_max_date": str(choke_max),
        "port_max_date": str(port_max),
        "chokepoint_join_coverage": round(choke_cov, 4),
        "port_join_coverage": round(port_cov, 4) if port_cov is not None else None,
    }
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description="Freight Radar PortWatch backfill")
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH))
    ap.add_argument("--days", type=int, default=BACKFILL_DAYS)
    ap.add_argument(
        "--incremental",
        action="store_true",
        help=f"trailing-{INCREMENTAL_REPULL_DAYS}d re-pull instead of full backfill",
    )
    ap.add_argument("--no-ports", dest="with_ports", action="store_false")
    args = ap.parse_args()

    days = INCREMENTAL_REPULL_DAYS if args.incremental else args.days
    print(f"Freight Radar backfill -> {args.db}  (days={days}, ports={args.with_ports})")
    summary = asyncio.run(
        run_backfill(db_path=args.db, days=days, with_ports=args.with_ports)
    )

    print("\n=== RECEIPT ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    cov_ok = summary["chokepoint_join_coverage"] >= MIN_JOIN_COVERAGE and (
        summary["port_join_coverage"] is None
        or summary["port_join_coverage"] >= MIN_JOIN_COVERAGE
    )
    print(f"\n  join coverage >= {MIN_JOIN_COVERAGE}: {'PASS' if cov_ok else 'FAIL'}")
    raise SystemExit(0 if cov_ok else 1)


if __name__ == "__main__":
    main()
