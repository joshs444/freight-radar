"""Wave 0 LIVE contract test — the receipt.

Hits the real PortWatch endpoints and runs a small real backfill into a temp
DuckDB, then asserts the contract the whole app depends on:

  * the four layers respond and carry the fields/shape we expect,
  * ``date`` is an ISO 'YYYY-MM-DD' string upstream and stored as a real DATE,
  * ``max(date)`` is recent (data is fresh enough to be useful),
  * the mandatory daily->reference ``portid`` join resolves >= 95%.

Run with:  python -m pytest tests/test_portwatch_contract.py -m live -v
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import pytest

from freight_radar.arcgis import ArcGISClient
from freight_radar.backfill import run_backfill
from freight_radar.config import MIN_JOIN_COVERAGE, SERVICES
from freight_radar.storage.db import connect, join_coverage

pytestmark = pytest.mark.live

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


async def test_reference_layers_have_geometry():
    """28 chokepoints + ~2065 ports, every row carrying WGS84 lat/lon."""
    async with ArcGISClient() as client:
        choke = await client.query_all(
            SERVICES["chokepoints_db"], out_fields="portid,lat,lon"
        )
        ports = await client.query_all(
            SERVICES["ports_db"], out_fields="portid,lat,lon"
        )
    assert len(choke) == 28, f"expected 28 chokepoints, got {len(choke)}"
    assert len(ports) > 2000, f"expected ~2065 ports, got {len(ports)}"
    for label, rows in (("chokepoints", choke), ("ports", ports)):
        bad = [r for r in rows if r.get("lat") is None or r.get("lon") is None]
        assert not bad, f"{label}: {len(bad)} rows missing lat/lon"


async def test_daily_date_is_recent_iso_string():
    """Upstream ``date`` is an ISO string and the latest day is recent."""
    async with ArcGISClient() as client:
        rows = await client.query_all(
            SERVICES["daily_chokepoints"],
            out_fields="date,portid,n_total",
            order_by="date DESC",
        )
    latest = rows[0]["date"]
    assert isinstance(latest, str) and ISO_DATE.match(latest), f"date not ISO str: {latest!r}"
    max_date = max(date.fromisoformat(r["date"]) for r in rows[:200])
    assert max_date >= date.today() - timedelta(days=30), f"stale: max date {max_date}"


async def test_pagination_exceeds_single_page():
    """The daily layer is larger than one 1000-row page — paging must work."""
    async with ArcGISClient() as client:
        end = date.today()
        start = end - timedelta(days=20)
        rows = await client.query_date_window(
            SERVICES["daily_ports"], start, end, out_fields="portid,date,portcalls"
        )
    assert len(rows) > 1000, f"pagination susp: only {len(rows)} rows for 20d of ports"


async def test_small_backfill_and_join_coverage(tmp_path):
    """End-to-end receipt: a real 14-day backfill yields a queryable DuckDB
    where max(date) is recent, date is a true DATE, and both joins clear 95%."""
    db_path = tmp_path / "contract.duckdb"
    summary = await run_backfill(db_path=db_path, days=14, with_ports=True)

    assert summary["chokepoint_rows"] > 0
    assert summary["port_rows"] > 1000

    con = connect(db_path)
    try:
        # date stored as a real DATE (DuckDB returns datetime.date, not str)
        d = con.execute("SELECT max(date) FROM fct_chokepoint_daily").fetchone()[0]
        assert isinstance(d, date), f"date not stored as DATE: {type(d)}"
        assert d >= date.today() - timedelta(days=30), f"stale max date {d}"

        choke_cov = join_coverage(con, "fct_chokepoint_daily", "dim_chokepoint")
        port_cov = join_coverage(con, "fct_port_daily", "dim_port")
        assert choke_cov >= MIN_JOIN_COVERAGE, f"chokepoint join {choke_cov:.3f} < {MIN_JOIN_COVERAGE}"
        assert port_cov >= MIN_JOIN_COVERAGE, f"port join {port_cov:.3f} < {MIN_JOIN_COVERAGE}"

        # provenance recorded
        runs = con.execute("SELECT count(*) FROM meta_ingest_runs").fetchone()[0]
        assert runs >= 1
        src = con.execute(
            "SELECT status, max_data_date FROM meta_source_status WHERE source='portwatch'"
        ).fetchone()
        assert src is not None and src[0] == "ok"
    finally:
        con.close()
