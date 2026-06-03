"""CLI: run the detection brain over all entities and publish real flags.

    python -m freight_radar.detect.run_detection

Connects DuckDB -> loads each entity's daily series -> runs STL+rolling-z detection
-> upserts ``fct_flags`` (INSERT OR REPLACE, dedup-stable per ISO week) -> overwrites
``frontend/public/data/flags.json`` with the detected flags, severity-DESC. Prints a
receipt (counts by kind + the top-5 flags with their real numbers).
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

import duckdb
import pandas as pd

from ..config import DEFAULT_DB_PATH, REPO_ROOT
from .detectors import DetectionConfig, Flag, detect_series, load_config

FLAGS_SCHEMA = Path(__file__).resolve().parent / "flags_schema.sql"
FLAGS_JSON = REPO_ROOT / "frontend" / "public" / "data" / "flags.json"

# Keys the frontend requires (export_snapshot.py Flag contract). asdict(Flag)
# already produces exactly this superset; we keep the order explicit for the file.
FLAG_KEYS = (
    "flag_id", "kind", "entity", "portid", "lat", "lon", "severity",
    "headline", "brief_md", "metric", "value", "baseline", "pct_change",
    "zscore", "as_of", "source", "method", "lifecycle",
)


def _econ_weights(vessel_counts: pd.Series) -> dict[str, float]:
    """Map portid -> 0.6..1.0 from the vessel_count_total percentile rank."""
    pct = vessel_counts.rank(pct=True)  # 0..1
    return {pid: 0.6 + 0.4 * float(p) for pid, p in pct.items()}


def _detect_chokepoints(con: duckdb.DuckDBPyConnection, cfg: DetectionConfig) -> list[Flag]:
    dims = con.execute(
        "SELECT portid, fullname, lat, lon, vessel_count_total FROM dim_chokepoint"
    ).df().set_index("portid")
    weights = _econ_weights(dims["vessel_count_total"])
    daily = con.execute(
        "SELECT portid, date, n_total FROM fct_chokepoint_daily ORDER BY portid, date"
    ).df()

    flags: list[Flag] = []
    for portid, grp in daily.groupby("portid"):
        if portid not in dims.index:
            continue
        d = dims.loc[portid]
        series = pd.Series(grp["n_total"].to_numpy(), index=pd.to_datetime(grp["date"]))
        flag = detect_series(
            portid=portid,
            entity=str(d["fullname"]),
            entity_type="chokepoint",
            metric="n_total",
            values=series,
            as_of=series.index[-1].date(),
            cfg=cfg,
            lat=float(d["lat"]) if pd.notna(d["lat"]) else None,
            lon=float(d["lon"]) if pd.notna(d["lon"]) else None,
            econ_weight=weights.get(portid, 1.0),
            unit="vessels",
        )
        if flag:
            flags.append(flag)
    return flags


def _detect_ports(con: duckdb.DuckDBPyConnection, cfg: DetectionConfig) -> list[Flag]:
    dims = con.execute(
        """
        SELECT portid, portname, fullname, lat, lon, vessel_count_total
        FROM dim_port
        WHERE lat IS NOT NULL AND lon IS NOT NULL
        ORDER BY vessel_count_total DESC
        LIMIT ?
        """,
        [cfg.top_n_ports],
    ).df().set_index("portid")
    weights = _econ_weights(dims["vessel_count_total"])
    daily = con.execute(
        """
        SELECT portid, date, portcalls_total
        FROM fct_port_daily
        WHERE portid IN (SELECT portid FROM dim_port
                         WHERE lat IS NOT NULL AND lon IS NOT NULL
                         ORDER BY vessel_count_total DESC LIMIT ?)
        ORDER BY portid, date
        """,
        [cfg.top_n_ports],
    ).df()

    flags: list[Flag] = []
    for portid, grp in daily.groupby("portid"):
        if portid not in dims.index:
            continue
        d = dims.loc[portid]
        name = str(d["portname"]) if pd.notna(d["portname"]) else str(d["fullname"])
        series = pd.Series(
            grp["portcalls_total"].to_numpy(), index=pd.to_datetime(grp["date"])
        )
        flag = detect_series(
            portid=portid,
            entity=name,
            entity_type="port",
            metric="portcalls_total",
            values=series,
            as_of=series.index[-1].date(),
            cfg=cfg,
            lat=float(d["lat"]),
            lon=float(d["lon"]),
            econ_weight=weights.get(portid, 1.0),
            unit="port calls",
        )
        if flag:
            flags.append(flag)
    return flags


def _upsert_flags(con: duckdb.DuckDBPyConnection, flags: list[Flag]) -> None:
    con.execute(FLAGS_SCHEMA.read_text())
    if not flags:
        return
    detected = date.today()
    now = datetime.now()
    rows = [
        {
            **asdict(f),
            "as_of": date.fromisoformat(f.as_of),
            "detected_date": detected,
            "computed_at": now,
        }
        for f in flags
    ]
    df = pd.DataFrame(rows)
    cols = ", ".join(f'"{c}"' for c in df.columns)
    con.register("_flags_src", df)
    try:
        con.execute(
            f"INSERT OR REPLACE INTO fct_flags ({cols}) SELECT {cols} FROM _flags_src"
        )
    finally:
        con.unregister("_flags_src")


def _write_json(flags: list[Flag]) -> None:
    flags_sorted = sorted(flags, key=lambda f: f.severity, reverse=True)
    payload = [{k: asdict(f)[k] for k in FLAG_KEYS} for f in flags_sorted]
    FLAGS_JSON.parent.mkdir(parents=True, exist_ok=True)
    FLAGS_JSON.write_text(json.dumps(payload, indent=2))


def run(db_path=DEFAULT_DB_PATH) -> list[Flag]:
    cfg = load_config()
    con = duckdb.connect(str(db_path))
    try:
        flags = _detect_chokepoints(con, cfg) + _detect_ports(con, cfg)
        _upsert_flags(con, flags)
    finally:
        con.close()
    _write_json(flags)
    return flags


def _receipt(flags: list[Flag]) -> None:
    by_kind: dict[str, int] = {}
    for f in flags:
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
    print("=== detection receipt ===")
    print(f"  total flags: {len(flags)}")
    for kind, n in sorted(by_kind.items()):
        print(f"    {kind}: {n}")
    print(f"  flags.json: {FLAGS_JSON}")
    print("  top 5 by severity:")
    for f in sorted(flags, key=lambda x: x.severity, reverse=True)[:5]:
        print(
            f"    [{f.severity:3d}] {f.kind:28s} {f.entity:22s} "
            f"value={f.value:g} baseline={f.baseline:g} "
            f"pct={f.pct_change:+g}% z={f.zscore:+g} as_of={f.as_of}"
        )


if __name__ == "__main__":
    _receipt(run())
