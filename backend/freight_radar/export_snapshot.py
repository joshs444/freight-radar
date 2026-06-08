"""One-shot exporter: DuckDB -> static JSON the frontend reads.

Emits three files into ``frontend/public/data/``:

  snapshot.json  {as_of, source, chokepoints[], ports[]}   -- glow by real activity
  lanes.json     [{name, from:[lon,lat], to:[lon,lat], intensity}]  -- hardcoded arcs
  flags.json     [Flag]  -- severity-ranked "current issues"

Flag contract (shared with Wave 2's real detector — keep these keys stable):
  {
    "flag_id": str, "kind": str, "entity": str, "portid": str,
    "severity": int(0..100), "headline": str, "brief_md": str,
    "metric": str, "value": float, "baseline": float,
    "pct_change": float, "zscore": float,
    "as_of": "YYYY-MM-DD", "source": str, "method": str, "lifecycle": str
  }

Wave 1 flags use a simple recent-vs-28-day-mean preview (method clearly labeled);
Wave 2 overwrites flags.json with STL+z-score detected anomalies of the same shape.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import duckdb

from .config import DEFAULT_DB_PATH, REPO_ROOT
from .registry.layers import root_source as _root_source

OUT_DIR = REPO_ROOT / "frontend" / "public" / "data"
# The snapshot IS the cited PortWatch root — read its identity from the registry SSOT, not a
# parallel literal, so the source name can never silently diverge from the catalog/ledger (P0-B).
SOURCE = f"{_root_source('snapshot').name} — daily granularity, refreshed weekly"

# The 5 leaf vessel types PortWatch breaks every count into. They sum *exactly*
# to the corresponding `*_total` (container+dry_bulk+general_cargo+roro+tanker),
# so a cargo-mix built from them is internally consistent with the headline total.
CARGO_TYPES = ("container", "tanker", "dry_bulk", "general_cargo", "roro")


def _cargo_mix(r, prefix: str) -> dict | None:
    """{type: count} over the 5 leaf vessel types from ``{prefix}{type}`` columns.

    ``prefix`` is ``n_`` for chokepoint transits, ``portcalls_`` for port calls.
    None when the row carries no breakdown (so the frontend can skip the block).
    """
    mix = {}
    for t in CARGO_TYPES:
        v = r.get(f"{prefix}{t}")
        mix[t] = int(v) if v is not None else 0
    return mix if sum(mix.values()) > 0 else None

# Hardcoded major ocean lanes (great-circle arcs). [lon, lat] endpoints.
LANES = [
    {"name": "Asia–Europe (Shanghai→Suez)", "from": [121.5, 31.2], "to": [32.44, 30.59], "intensity": 0.95},
    {"name": "Suez→Rotterdam", "from": [32.44, 30.59], "to": [4.13, 51.95], "intensity": 0.9},
    {"name": "Transpacific (Shanghai→LA)", "from": [121.5, 31.2], "to": [-118.27, 33.74], "intensity": 0.85},
    {"name": "Singapore→Suez", "from": [103.85, 1.29], "to": [32.44, 30.59], "intensity": 0.8},
    {"name": "Gulf→Asia (Hormuz→Singapore)", "from": [56.4, 26.6], "to": [103.85, 1.29], "intensity": 0.75},
    {"name": "Cape route (Singapore→Cape→Rotterdam)", "from": [103.85, 1.29], "to": [18.42, -34.36], "intensity": 0.5},
    {"name": "Cape→Rotterdam", "from": [18.42, -34.36], "to": [4.13, 51.95], "intensity": 0.5},
    {"name": "Panama (Shanghai→Panama→US East)", "from": [121.5, 31.2], "to": [-79.92, 9.0], "intensity": 0.6},
    {"name": "Panama→New York", "from": [-79.92, 9.0], "to": [-74.0, 40.6], "intensity": 0.55},
    {"name": "Malacca (Singapore→Hormuz)", "from": [103.85, 1.29], "to": [56.4, 26.6], "intensity": 0.7},
]


def _chokepoints(con) -> list[dict]:
    rows = con.execute(
        """
        WITH latest AS (SELECT max(date) AS md FROM fct_chokepoint_daily),
        recent AS (
            SELECT portid,
                   max(date) AS latest_date,
                   arg_max(n_total, date) AS n_total,
                   arg_max(n_container, date) AS n_container,
                   arg_max(n_tanker, date) AS n_tanker,
                   arg_max(n_dry_bulk, date) AS n_dry_bulk,
                   arg_max(n_general_cargo, date) AS n_general_cargo,
                   arg_max(n_roro, date) AS n_roro,
                   arg_max(capacity_total, date) AS capacity_total
            FROM fct_chokepoint_daily GROUP BY portid
        ),
        baseline AS (
            SELECT f.portid,
                   avg(f.n_total) AS base_mean,
                   stddev_samp(f.n_total) AS base_std
            FROM fct_chokepoint_daily f, latest l
            WHERE f.date >= l.md - 28 AND f.date < l.md
            GROUP BY f.portid
        )
        SELECT d.portid, d.fullname AS name, d.country, d.lat, d.lon,
               d.industry_top1, d.vessel_count_total,
               r.latest_date, r.n_total, r.n_container, r.n_tanker, r.n_dry_bulk,
               r.n_general_cargo, r.n_roro,
               r.capacity_total, b.base_mean, b.base_std
        FROM dim_chokepoint d
        JOIN recent r USING (portid)
        LEFT JOIN baseline b USING (portid)
        ORDER BY r.n_total DESC
        """
    ).df()
    rows = rows.astype(object)
    rows = rows.where(rows.notna(), None)  # NaN/NA -> None so JSON stays valid

    out = []
    for _, r in rows.iterrows():
        base = float(r["base_mean"]) if r["base_mean"] is not None else None
        std = float(r["base_std"]) if r["base_std"] else None
        n = float(r["n_total"])
        pct = round((n - base) / base * 100, 1) if base else None
        z = round((n - base) / std, 2) if (base is not None and std) else None
        cap = r["capacity_total"]
        # avg cargo size of transiting vessels = total transiting DWT / vessel count.
        # A fleet-mix figure (bigger/smaller ships), NOT utilisation — capacity is a
        # flow, not a ceiling. See the A3 detector (chokepoint_vessel_size_shift).
        avg_size = int(round(cap / n)) if (cap is not None and n > 0) else None
        out.append(
            {
                "portid": r["portid"],
                "name": r["name"],
                "country": r["country"],
                "lat": float(r["lat"]),
                "lon": float(r["lon"]),
                "industry": r["industry_top1"],
                "n_total": int(n),
                "n_container": int(r["n_container"]),
                "n_tanker": int(r["n_tanker"]),
                "n_dry_bulk": int(r["n_dry_bulk"]),
                "capacity_total": int(cap) if cap is not None else None,
                "avg_vessel_size_dwt": avg_size,
                "cargo_mix": _cargo_mix(r, "n_"),
                "baseline": round(base, 1) if base else None,
                "pct_change": pct,
                "zscore": z,
                "as_of": str(r["latest_date"])[:10],  # DATE -> 'YYYY-MM-DD' (drop time)
            }
        )
    return out


def _ports(con) -> list[dict]:
    rows = con.execute(
        """
        WITH recent AS (
            SELECT portid, max(date) AS latest_date,
                   arg_max(portcalls_total, date) AS portcalls,
                   arg_max(portcalls_container, date) AS portcalls_container,
                   arg_max(portcalls_tanker, date) AS portcalls_tanker,
                   arg_max(portcalls_dry_bulk, date) AS portcalls_dry_bulk,
                   arg_max(portcalls_general_cargo, date) AS portcalls_general_cargo,
                   arg_max(portcalls_roro, date) AS portcalls_roro
            FROM fct_port_daily GROUP BY portid
        )
        SELECT d.portid, d.portname AS name, d.country, d.lat, d.lon,
               d.vessel_count_total,
               d.share_country_maritime_import, d.share_country_maritime_export,
               r.latest_date,
               r.portcalls,
               r.portcalls_container, r.portcalls_tanker, r.portcalls_dry_bulk,
               r.portcalls_general_cargo, r.portcalls_roro
        FROM dim_port d JOIN recent r USING (portid)
        WHERE d.lat IS NOT NULL AND d.lon IS NOT NULL
        """
    ).df()
    rows = rows.astype(object)
    rows = rows.where(rows.notna(), None)  # NaN/NA -> None so JSON stays valid
    return [
        {
            "portid": r["portid"],
            "name": r["name"],
            "country": r["country"],
            "lat": float(r["lat"]),
            "lon": float(r["lon"]),
            # the port's own latest date — port data trails the chokepoint half by the
            # upstream publish lag, so don't let the snapshot's headline as_of imply it.
            "as_of": str(r["latest_date"])[:10],
            "vessels": int(r["vessel_count_total"]) if r["vessel_count_total"] is not None else 0,
            "portcalls": int(r["portcalls"]) if r["portcalls"] is not None else 0,
            "cargo_mix": _cargo_mix(r, "portcalls_"),
            # national-dependence: this port's share of its country's maritime trade
            # (0-100 %, IMF systemic-importance). None when absent. (Phase B)
            "share_import": round(float(r["share_country_maritime_import"]), 1)
            if r["share_country_maritime_import"] is not None else None,
            "share_export": round(float(r["share_country_maritime_export"]), 1)
            if r["share_country_maritime_export"] is not None else None,
        }
        for _, r in rows.iterrows()
    ]


def _preview_flags(chokepoints: list[dict], as_of: str) -> list[dict]:
    """Wave-1 honest preview flags: top movers by |z| vs the 28-day mean.

    Real STL+z-score detection (Wave 2) overwrites flags.json with the same shape.
    """
    scored = [c for c in chokepoints if c["zscore"] is not None and c["baseline"]]
    scored.sort(key=lambda c: abs(c["zscore"]), reverse=True)
    flags = []
    for c in scored[:6]:
        z = c["zscore"]
        pct = c["pct_change"]
        direction = "below" if pct < 0 else "above"
        # honest severity: scale |z| (cap at ~4) onto 0..100
        severity = int(min(abs(z) / 4.0, 1.0) * 100)
        kind = "chokepoint_transit_drop" if pct < 0 else "chokepoint_transit_surge"
        headline = f"{c['name']} transit {abs(pct):.0f}% {direction} its 28-day norm"
        brief = (
            f"**{c['name']}** handled **{c['n_total']} vessels** on {c['as_of']}, "
            f"vs a 28-day average of **{c['baseline']:.0f}/day** "
            f"({pct:+.0f}%, z = {z:+.1f}). Top industry: {c['industry'] or 'n/a'}.\n\n"
            f"_Preview signal: latest day vs 28-day mean. Full STL anomaly "
            f"detection lands in the detection-brain release._"
        )
        flags.append(
            {
                "flag_id": f"preview-{c['portid']}-{as_of}",
                "kind": kind,
                "entity": c["name"],
                "portid": c["portid"],
                "lat": c["lat"],
                "lon": c["lon"],
                "severity": severity,
                "headline": headline,
                "brief_md": brief,
                "metric": "vessels/day",
                "value": float(c["n_total"]),
                "baseline": c["baseline"],
                "pct_change": pct,
                "zscore": z,
                "as_of": c["as_of"],
                "source": SOURCE,
                "method": "preview: latest vs 28-day mean",
                "lifecycle": "new",
            }
        )
    flags.sort(key=lambda f: f["severity"], reverse=True)
    return flags


def export(db_path=DEFAULT_DB_PATH, out_dir: Path = OUT_DIR, write_flags: bool = True) -> dict:
    """Write snapshot.json + lanes.json (+ preview flags.json by default).

    The Temporal pipeline passes ``write_flags=False`` because real STL detection
    (run_detection) owns flags.json there; the preview flags are only for the
    standalone Wave-1 path where no detector has run yet.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(db_path))
    try:
        chokepoints = _chokepoints(con)
        ports = _ports(con)
        as_of = max(c["as_of"] for c in chokepoints)
        flags = _preview_flags(chokepoints, as_of) if write_flags else []
    finally:
        con.close()

    snapshot = {
        "as_of": as_of,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE,
        "chokepoints": chokepoints,
        "ports": ports,
    }
    (out_dir / "snapshot.json").write_text(json.dumps(snapshot, separators=(",", ":")))
    (out_dir / "lanes.json").write_text(json.dumps(LANES, separators=(",", ":")))
    if write_flags:
        (out_dir / "flags.json").write_text(json.dumps(flags, indent=2))

    return {
        "out_dir": str(out_dir),
        "as_of": as_of,
        "chokepoints": len(chokepoints),
        "ports": len(ports),
        "lanes": len(LANES),
        "flags": len(flags),
        "snapshot_kb": round((out_dir / "snapshot.json").stat().st_size / 1024, 1),
    }


if __name__ == "__main__":
    summary = export()
    print("=== export receipt ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")
