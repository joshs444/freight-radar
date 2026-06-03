"""Exporter for the time-scrubber + per-entity history sparklines.

Writes ``timeseries.json`` with:
  - ``dates``/``chokepoints``/``flags`` — drive the globe time-scrubber (chokepoints only)
  - ``series`` — per-entity daily history keyed by portid (28 chokepoints + flagged
    ports + top ports), so the feed can render a sparkline + the real history that
    makes "why is this critical vs normal" self-evident at a glance.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from .config import DEFAULT_DB_PATH, PUBLISH_DIR

WINDOW_DAYS = 120
TOP_PORTS = 45


def _align(by_date: dict, dates: list[str]) -> list[int]:
    out, last = [], 0
    for dt in dates:
        v = by_date.get(dt)
        if v is not None and not pd.isna(v):
            last = int(v)
        out.append(last)
    return out


def _build_series(con: duckdb.DuckDBPyConnection, dates: list[str]) -> dict:
    series: dict[str, dict] = {}

    # chokepoints (n_total)
    cdf = con.execute(
        """
        SELECT c.portid, d.fullname AS name, CAST(c.date AS VARCHAR) AS date, c.n_total AS v
        FROM fct_chokepoint_daily c JOIN dim_chokepoint d USING (portid)
        WHERE c.date > (SELECT max(date) - ? FROM fct_chokepoint_daily)
        ORDER BY c.portid, c.date
        """,
        [WINDOW_DAYS],
    ).df()
    for portid, grp in cdf.groupby("portid"):
        series[portid] = {
            "name": str(grp["name"].iloc[0]),
            "metric": "vessels/day",
            "values": _align(dict(zip(grp["date"], grp["v"])), dates),
        }

    # ports to include: flagged ports + top-N by vessel_count
    flagged = [r[0] for r in con.execute(
        "SELECT DISTINCT portid FROM fct_flags WHERE portid LIKE 'port%'"
    ).fetchall()]
    top = [r[0] for r in con.execute(
        "SELECT portid FROM dim_port WHERE lat IS NOT NULL ORDER BY vessel_count_total DESC LIMIT ?",
        [TOP_PORTS],
    ).fetchall()]
    port_ids = list(dict.fromkeys(flagged + top))
    if port_ids:
        ph = ", ".join("?" for _ in port_ids)
        pdf = con.execute(
            f"""
            SELECT p.portid, d.portname AS name, CAST(p.date AS VARCHAR) AS date,
                   p.portcalls_total AS v
            FROM fct_port_daily p JOIN dim_port d USING (portid)
            WHERE p.portid IN ({ph})
              AND p.date > (SELECT max(date) - ? FROM fct_port_daily)
            ORDER BY p.portid, p.date
            """,
            [*port_ids, WINDOW_DAYS],
        ).df()
        for portid, grp in pdf.groupby("portid"):
            series[portid] = {
                "name": str(grp["name"].iloc[0]),
                "metric": "port calls/day",
                "values": _align(dict(zip(grp["date"], grp["v"])), dates),
            }

    return series


def export_timeseries(db_path=DEFAULT_DB_PATH, out_dir: Path = PUBLISH_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        max_date = con.execute("SELECT max(date) FROM fct_chokepoint_daily").fetchone()[0]
        rows = con.execute(
            """
            SELECT d.portid, d.fullname AS name, d.lat, d.lon,
                   CAST(c.date AS VARCHAR) AS date, c.n_total
            FROM fct_chokepoint_daily c JOIN dim_chokepoint d USING (portid)
            WHERE c.date > (SELECT max(date) - ? FROM fct_chokepoint_daily)
            ORDER BY d.portid, c.date
            """,
            [WINDOW_DAYS],
        ).df()
        flag_rows = con.execute(
            """
            SELECT flag_id, entity, portid, lat, lon, severity, kind, headline,
                   CAST(as_of AS VARCHAR) AS as_of
            FROM fct_flags
            WHERE as_of > (SELECT max(date) - ? FROM fct_chokepoint_daily)
            ORDER BY as_of
            """,
            [WINDOW_DAYS],
        ).fetchall()

        dates = sorted(rows["date"].unique().tolist())
        meta = rows.groupby("portid").first()[["name", "lat", "lon"]]
        chokepoints = []
        for portid, grp in rows.groupby("portid"):
            m = meta.loc[portid]
            chokepoints.append({
                "portid": portid, "name": str(m["name"]),
                "lat": float(m["lat"]), "lon": float(m["lon"]),
                "values": _align(dict(zip(grp["date"], grp["n_total"])), dates),
            })
        series = _build_series(con, dates)
    finally:
        con.close()

    flags = [
        {"flag_id": r[0], "entity": r[1], "portid": r[2],
         "lat": float(r[3]) if r[3] is not None else None,
         "lon": float(r[4]) if r[4] is not None else None,
         "severity": int(r[5]), "kind": r[6], "headline": r[7], "as_of": r[8]}
        for r in flag_rows if r[3] is not None and r[4] is not None
    ]

    payload = {"dates": dates, "max_date": str(max_date),
               "chokepoints": chokepoints, "flags": flags, "series": series}
    path = out_dir / "timeseries.json"
    path.write_text(json.dumps(payload, separators=(",", ":")))
    return {"out": str(path), "dates": len(dates), "chokepoints": len(chokepoints),
            "series": len(series), "flags_in_window": len(flags),
            "kb": round(path.stat().st_size / 1024, 1)}


if __name__ == "__main__":
    print(json.dumps(export_timeseries(), indent=2))
