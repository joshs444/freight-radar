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
from .cape_reroute import detect_cape_reroute
from .detectors import DetectionConfig, Flag, detect_series, load_config
from .holidays import apply_holiday_suppression
from .lifecycle import apply_lifecycle
from .persistent import detect_persistent

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
    series_by_id: dict[str, pd.Series] = {}
    for portid, grp in daily.groupby("portid"):
        if portid not in dims.index:
            continue
        d = dims.loc[portid]
        series = pd.Series(grp["n_total"].to_numpy(), index=pd.to_datetime(grp["date"]))
        series_by_id[portid] = series
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

    # Persistent level-shift pass: catch sustained disruptions the fresh detector
    # (28-day baseline) has adapted to and now reads as "normal" (e.g. Hormuz).
    flagged = {f.portid for f in flags}
    for portid, series in series_by_id.items():
        if portid in flagged:
            continue
        d = dims.loc[portid]
        pf = detect_persistent(
            portid=portid,
            entity=str(d["fullname"]),
            values=series,
            cfg=cfg,
            lat=float(d["lat"]) if pd.notna(d["lat"]) else None,
            lon=float(d["lon"]) if pd.notna(d["lon"]) else None,
            econ_weight=weights.get(portid, 1.0),
            unit="vessels",
        )
        if pf:
            flags.append(pf)
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


def _detect_cape_reroute(
    con: duckdb.DuckDBPyConnection, cfg: DetectionConfig
) -> list[Flag]:
    """Wave 5: one cape_reroute flag iff Red Sea is down while the Cape is up.

    Pulls the combined (summed) Suez+Bab daily series and the Cape series, joins on
    date so the windows align, and delegates to ``detect_cape_reroute``. Returns []
    when the data shows no divergence (the honest default on a calm window).
    """
    rs_ids = list(cfg.red_sea_portids)
    placeholders = ", ".join("?" for _ in rs_ids)
    rs = con.execute(
        f"""
        SELECT date, SUM(n_total) AS n_total
        FROM fct_chokepoint_daily
        WHERE portid IN ({placeholders})
        GROUP BY date ORDER BY date
        """,
        rs_ids,
    ).df()
    cape = con.execute(
        "SELECT date, n_total FROM fct_chokepoint_daily WHERE portid = ? ORDER BY date",
        [cfg.cape_portid],
    ).df()
    if rs.empty or cape.empty:
        return []
    geo = con.execute(
        "SELECT lat, lon FROM dim_chokepoint WHERE portid = ?", [cfg.cape_portid]
    ).fetchone()
    cape_lat = float(geo[0]) if geo and geo[0] is not None else None
    cape_lon = float(geo[1]) if geo and geo[1] is not None else None

    rs_s = pd.Series(rs["n_total"].to_numpy(), index=pd.to_datetime(rs["date"]))
    cape_s = pd.Series(cape["n_total"].to_numpy(), index=pd.to_datetime(cape["date"]))
    as_of = max(rs_s.index[-1], cape_s.index[-1]).date()
    flag = detect_cape_reroute(
        red_sea=rs_s,
        cape=cape_s,
        cape_lat=cape_lat,
        cape_lon=cape_lon,
        as_of=as_of,
        cfg=cfg,
    )
    return [flag] if flag else []


def _load_prior_flags(con: duckdb.DuckDBPyConnection) -> dict[str, dict]:
    """Most-recent prior ``fct_flags`` state keyed by flag_id (for lifecycle).

    Reads the rows from the latest ``detected_date`` only, excluding already-
    resolved tombstones (so a cleared flag doesn't keep re-resolving). Empty when
    the table doesn't exist yet (first ever run).
    """
    con.execute(FLAGS_SCHEMA.read_text())
    try:
        rows = con.execute(
            """
            SELECT * FROM fct_flags
            WHERE detected_date = (SELECT max(detected_date) FROM fct_flags)
              AND COALESCE(lifecycle, '') <> 'resolved'
            """
        ).df()
    except duckdb.Error:
        return {}
    return {r["flag_id"]: r.to_dict() for _, r in rows.iterrows()}


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


def _write_json(flags: list[Flag], path: Path = FLAGS_JSON) -> None:
    flags_sorted = sorted(flags, key=lambda f: f.severity, reverse=True)
    payload = [{k: asdict(f)[k] for k in FLAG_KEYS} for f in flags_sorted]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def run(db_path=DEFAULT_DB_PATH, flags_json: Path | None = None) -> list[Flag]:
    """Detect, gate, label lifecycle, suppress holidays -> upsert + publish.

    Wave-5 pipeline (order matters): read the prior fct_flags state BEFORE writing
    -> run the (change-point-gated) chokepoint/port detectors + the Cape-reroute
    detector -> downweight benign holiday dips -> label lifecycle (and emit resolved
    tombstones) -> upsert + write flags.json. Public API is unchanged: returns the
    final ``list[Flag]`` (now carrying real lifecycle labels), and the JSON keeps
    the 18-key contract.
    """
    cfg = load_config()
    con = duckdb.connect(str(db_path))
    try:
        prior = _load_prior_flags(con)
        detected = (
            _detect_chokepoints(con, cfg)
            + _detect_ports(con, cfg)
            + _detect_cape_reroute(con, cfg)
        )
        detected = apply_holiday_suppression(detected, cfg)
        flags = apply_lifecycle(detected, prior, cfg)
        _upsert_flags(con, flags)
    finally:
        con.close()
    _write_json(flags, flags_json or FLAGS_JSON)
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
