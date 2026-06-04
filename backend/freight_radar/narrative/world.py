"""World Today — a high-level pulse of global ocean freight, with visible trends.

Answers "what's going on in the world right now": how many ships are transiting
the chokepoints, how many are calling at ports, and how much cargo has been
delivered (imports) and shipped (exports) — each with a 30-day sparkline and a
today-vs-trailing-week trend so the movement is actually visible.

All figures are real daily sums from the local DuckDB (the same tables the rest of
the app reads). Cargo tonnages are PortWatch's trade-volume estimates (metric tons),
labelled as estimates in the UI.
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

SPARK_DAYS = 30
TREND_WINDOW = 7  # today vs the mean of the prior 7 days


def _series(rows: list[tuple]) -> tuple[list[str], dict]:
    """rows = [(date, col1, col2, ...)] → (dates, {idx: [values]})."""
    dates = [str(r[0]) for r in rows]
    cols = {}
    for ci in range(1, len(rows[0]) if rows else 0):
        cols[ci] = [float(r[ci]) if r[ci] is not None else 0.0 for r in rows]
    return dates, cols


def _metric(key, label, sublabel, unit, values, dates):
    if not values:
        return None
    today = values[-1]
    prior = values[-(TREND_WINDOW + 1):-1] if len(values) > TREND_WINDOW else values[:-1]
    base = sum(prior) / len(prior) if prior else today
    vs7 = round((today - base) / base * 100, 1) if base else 0.0
    return {
        "key": key, "label": label, "sublabel": sublabel, "unit": unit,
        "value": round(today, 1) if today < 100 else int(round(today)),
        "vs7_pct": vs7,
        "trend": "up" if vs7 > 1 else "down" if vs7 < -1 else "flat",
        "spark": [int(round(v)) for v in values[-SPARK_DAYS:]],
        "as_of": dates[-1],
    }


def compute(con: duckdb.DuckDBPyConnection) -> dict:
    # --- chokepoint transits (vessels/day, by class) over the window --------
    crows = con.execute(
        """
        SELECT CAST(date AS VARCHAR) AS d,
               sum(n_total)        AS total,
               sum(n_container)    AS container,
               sum(n_tanker)       AS tanker,
               sum(n_dry_bulk)     AS dry_bulk
        FROM fct_chokepoint_daily
        WHERE date > (SELECT max(date) - ? FROM fct_chokepoint_daily)
        GROUP BY date ORDER BY date
        """,
        [120],
    ).fetchall()
    cdates, ccols = _series(crows)

    # --- port calls + cargo delivered/shipped over the window ---------------
    prows = con.execute(
        """
        SELECT CAST(date AS VARCHAR) AS d,
               sum(portcalls_total) AS calls,
               sum(import_total)    AS delivered,
               sum(export_total)    AS shipped
        FROM fct_port_daily
        WHERE date > (SELECT max(date) - ? FROM fct_port_daily)
        GROUP BY date ORDER BY date
        """,
        [120],
    ).fetchall()
    pdates, pcols = _series(prows)

    ports_active = con.execute(
        "SELECT count(DISTINCT portid) FROM fct_port_daily WHERE date=(SELECT max(date) FROM fct_port_daily)"
    ).fetchone()[0]
    chokepoints = con.execute("SELECT count(*) FROM dim_chokepoint").fetchone()[0]

    metrics = [
        _metric("transits", "Ships in transit", f"through {chokepoints} chokepoints/day",
                "vessels", ccols.get(1, []), cdates),
        _metric("port_calls", "Port calls", f"ships arriving · {ports_active} ports",
                "calls", pcols.get(1, []), pdates),
        _metric("delivered", "Cargo delivered", "imports/day · PortWatch est.",
                "t", pcols.get(2, []), pdates),
        _metric("shipped", "Cargo shipped", "exports/day · PortWatch est.",
                "t", pcols.get(3, []), pdates),
    ]
    metrics = [m for m in metrics if m]

    # today's transit mix (vessel classes that have their own flag colors elsewhere)
    mix = {}
    if ccols:
        for name, ci in (("container", 2), ("tanker", 3), ("dry_bulk", 4)):
            vals = ccols.get(ci, [])
            if vals:
                mix[name] = int(round(vals[-1]))

    return {
        "available": bool(metrics),
        "as_of": cdates[-1] if cdates else None,
        "ports_as_of": pdates[-1] if pdates else None,
        "chokepoints": chokepoints,
        "ports_active": int(ports_active),
        "metrics": metrics,
        "transit_mix": mix,
        "source": "IMF PortWatch — daily granularity, refreshed weekly",
    }


def run(ctx) -> dict:
    con = duckdb.connect(str(ctx.db_path), read_only=True)
    try:
        payload = compute(con)
    finally:
        con.close()
    payload["generated_at"] = ctx.today
    (Path(ctx.out_dir) / "world.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "world", "sidecar": "world.json",
            "metrics": len(payload.get("metrics", []))}


if __name__ == "__main__":
    from ..config import db_path
    con = duckdb.connect(str(db_path()), read_only=True)
    print(json.dumps({k: v for k, v in compute(con).items() if k != "metrics"}, indent=2))
    for m in compute(con)["metrics"]:
        print(f"  {m['label']:18} {m['value']:>12} {m['unit']:8} {m['vs7_pct']:+.1f}% ({m['trend']})")
