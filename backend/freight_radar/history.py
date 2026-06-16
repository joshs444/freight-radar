"""History — "play through 2019 -> now".

Builds ``history.json``: the daily Global Ocean Freight Stress Index across PortWatch's
FULL record (verified 2019-01-01 -> present) plus each chokepoint's throughput, so the
frontend can animate the real shocks landing — COVID (spring 2020), the Ever Given
blocking Suez (Mar 2021), the Panama drought (2023), the Red Sea / Houthi crisis (late
2023->) — with dated, source-cited captions.

Honesty: every number is computed in Python from PortWatch daily transits, and the index
is the SAME breadth+depth composite the live view uses — we literally call
``narrative.stress.compute`` over the full window, no new index math. Event captions are
curated + cited (``config/historical_events.yaml``), never generated. The series is
downsampled to weekly for a small, smooth play-through (the events annotate the sharp
moments). 2015 isn't available; PortWatch starts 2019-01-01. Free / keyless (same source).
"""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date
from pathlib import Path

import pandas as pd
import yaml

from ._log import configure as configure_logging
from ._log import get_logger
from .arcgis import ArcGISClient
from .config import BACKEND_DIR, DEFAULT_DB_PATH, publish_dir
from .ingest.dims import load_dims
from .ingest.portwatch import stage_chokepoint_daily
from .narrative import stress
from .storage.db import connect
from .wap import promote

log = get_logger(__name__)

HISTORY_START = date(2019, 1, 1)
EVENTS_PATH = BACKEND_DIR / "config" / "historical_events.yaml"
NORMAL_PCTILE = stress.NORMAL_PCTILE  # 0.80 — keep the chokepoint "normal" identical


async def _pull_daily(db_path) -> pd.DataFrame:
    """Full 2019->today daily chokepoint throughput, joined to name/lat/lon."""
    con = connect(db_path)
    end = date.today()
    # Write-Audit-Publish: stage the full-history pull, audit it, then atomically
    # promote into fct_chokepoint_daily (same seam the backfill + durable path use).
    con.execute("DELETE FROM stg_chokepoint_daily")
    async with ArcGISClient() as client:
        await load_dims(con, client)
        await stage_chokepoint_daily(con, client, HISTORY_START, end)
    rows_loaded = promote(con, "stg_chokepoint_daily")["rows_promoted"]
    log.info("history: pulled %s daily chokepoint rows (%s -> %s)", rows_loaded, HISTORY_START, end)
    rows = con.execute(
        """
        SELECT c.portid, d.fullname AS name, d.lat AS lat, d.lon AS lon,
               CAST(c.date AS VARCHAR) AS date, c.n_total AS v, c.capacity_total AS cap
        FROM fct_chokepoint_daily c JOIN dim_chokepoint d USING (portid)
        WHERE c.date >= ?
        ORDER BY c.portid, c.date
        """,
        [HISTORY_START],
    ).fetchall()
    return pd.DataFrame(rows, columns=["portid", "name", "lat", "lon", "date", "v", "cap"])


def build_payload(df: pd.DataFrame, today: str) -> dict:
    """Daily stress (via the live engine) + weekly-downsampled arrays + curated events."""
    meta = df.drop_duplicates("portid").set_index("portid")[["name", "lat", "lon"]]
    # daily matrix [date x chokepoint], gaps carried forward so a missing day isn't a "0"
    wide = (
        df.pivot_table(index="date", columns="portid", values="v", aggfunc="sum")
        .sort_index()
        .ffill()
        .bfill()
    )
    daily_dates = list(wide.index)
    # long-window normal (full record) + capacity (DWT) basis per chokepoint, so the
    # history index uses the SAME anchored normal + DWT weighting as the live view (H1-C).
    # Capacity is optional — the real _pull_daily always supplies it; a frame without it
    # (e.g. a unit fixture) falls back to vessel-count weighting in stress.compute.
    normals = {pid: float(wide[pid].quantile(NORMAL_PCTILE)) for pid in wide.columns}
    if "cap" in df.columns:
        wide_cap = (
            df.pivot_table(index="date", columns="portid", values="cap", aggfunc="sum")
            .sort_index()
            .ffill()
            .bfill()
        )
        cap_normals = {pid: float(wide_cap[pid].quantile(NORMAL_PCTILE)) for pid in wide.columns}
    else:
        cap_normals = {pid: None for pid in wide.columns}
    daily_chokes = [
        {
            "portid": pid,
            "name": meta.loc[pid, "name"],
            "lat": float(meta.loc[pid, "lat"]),
            "lon": float(meta.loc[pid, "lon"]),
            "normal": normals[pid],
            "cap_normal": cap_normals[pid],
            "values": [float(x) for x in wide[pid].tolist()],
        }
        for pid in wide.columns
    ]
    # the SAME index the live view uses, computed daily over the full window
    s = stress.compute({"dates": daily_dates, "chokepoints": daily_chokes})

    # weekly downsample (mean) for a compact, smooth play-through
    idx = pd.to_datetime(wide.index)
    weekly = wide.set_axis(idx).resample("W").mean()
    stress_weekly = pd.Series(s["history"], index=idx).resample("W").mean().round(1)
    weekly_dates = [d.date().isoformat() for d in weekly.index]

    chokepoints = []
    for pid in wide.columns:
        chokepoints.append(
            {
                "portid": pid,
                "name": meta.loc[pid, "name"],
                "lat": float(meta.loc[pid, "lat"]),
                "lon": float(meta.loc[pid, "lon"]),
                "normal": round(normals[pid], 1),
                "values": [round(float(x)) for x in weekly[pid].tolist()],
            }
        )

    events = []
    if EVENTS_PATH.exists():
        raw_events = yaml.safe_load(EVENTS_PATH.read_text()).get("events", [])
        # PyYAML parses ISO dates into date objects — stringify them back for JSON
        events = [
            {k: (v.isoformat() if hasattr(v, "isoformat") else v) for k, v in e.items()}
            for e in raw_events
        ]

    return {
        "generated_at": today,
        "resolution": "weekly",
        "range": {"start": weekly_dates[0], "end": weekly_dates[-1]},
        "dates": weekly_dates,
        "stress": [float(x) for x in stress_weekly.tolist()],
        "chokepoints": chokepoints,
        "events": events,
        "method": (
            "Same breadth+depth composite as the live index (narrative.stress), computed "
            "daily over PortWatch's full record then averaged to weekly for the timeline."
        ),
        "source": "IMF PortWatch — daily chokepoint transits, 2019-01-01 to present (free, keyless).",
    }


async def build(db_path=DEFAULT_DB_PATH, today: str | None = None) -> dict:
    df = await _pull_daily(db_path)
    payload = build_payload(df, today or date.today().isoformat())
    out = publish_dir()
    (out / "history.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {
        "name": "history",
        "sidecar": "history.json",
        "weeks": len(payload["dates"]),
        "range": payload["range"],
        "peak_stress": max(payload["stress"]) if payload["stress"] else None,
    }


def main() -> None:
    configure_logging()
    ap = argparse.ArgumentParser(description="Build history.json (2019->now stress play-through)")
    ap.add_argument("--db", default=str(DEFAULT_DB_PATH))
    args = ap.parse_args()
    result = asyncio.run(build(db_path=Path(args.db)))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
