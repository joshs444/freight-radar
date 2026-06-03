"""Exporter for the time-scrubber: per-date chokepoint activity + flag firing dates.

Writes ``timeseries.json`` so the frontend can replay the trailing window — the
28 chokepoints' glow dims/brightens by each day's real vessel count, and a flag
pulses red on the actual date it was detected. Chokepoints only (28 series, small);
ports stay ambient during scrub.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from .config import DEFAULT_DB_PATH, PUBLISH_DIR

WINDOW_DAYS = 120


def export_timeseries(db_path=DEFAULT_DB_PATH, out_dir: Path = PUBLISH_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        max_date = con.execute("SELECT max(date) FROM fct_chokepoint_daily").fetchone()[0]
        rows = con.execute(
            """
            SELECT d.portid, d.fullname AS name, d.lat, d.lon,
                   CAST(c.date AS VARCHAR) AS date, c.n_total
            FROM fct_chokepoint_daily c
            JOIN dim_chokepoint d USING (portid)
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
    finally:
        con.close()

    dates = sorted(rows["date"].unique().tolist())
    meta = rows.groupby("portid").first()[["name", "lat", "lon"]]

    chokepoints = []
    for portid, grp in rows.groupby("portid"):
        by_date = dict(zip(grp["date"], grp["n_total"]))
        # align to the full window; forward-fill gaps, default 0
        series, last = [], 0
        for dt in dates:
            v = by_date.get(dt)
            last = int(v) if v is not None and not pd.isna(v) else last
            series.append(last)
        m = meta.loc[portid]
        chokepoints.append(
            {
                "portid": portid,
                "name": str(m["name"]),
                "lat": float(m["lat"]),
                "lon": float(m["lon"]),
                "values": series,
            }
        )

    flags = [
        {
            "flag_id": r[0], "entity": r[1], "portid": r[2],
            "lat": float(r[3]) if r[3] is not None else None,
            "lon": float(r[4]) if r[4] is not None else None,
            "severity": int(r[5]), "kind": r[6], "headline": r[7], "as_of": r[8],
        }
        for r in flag_rows
        if r[3] is not None and r[4] is not None
    ]

    payload = {
        "dates": dates,
        "max_date": str(max_date),
        "chokepoints": chokepoints,
        "flags": flags,
    }
    path = out_dir / "timeseries.json"
    path.write_text(json.dumps(payload, separators=(",", ":")))
    return {
        "out": str(path),
        "dates": len(dates),
        "chokepoints": len(chokepoints),
        "flags_in_window": len(flags),
        "kb": round(path.stat().st_size / 1024, 1),
    }


if __name__ == "__main__":
    print(json.dumps(export_timeseries(), indent=2))
