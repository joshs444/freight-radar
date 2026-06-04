"""Phase A2 — dominant-cargo-type port detector tests.

Two layers, both deterministic (synthetic series; the integration test uses an
in-memory DuckDB, no network):

  * the ``_dominant_cargo_flag`` helper fires on a container-only drop while the
    blended total holds flat — and refuses when no type is dominant enough; and
  * the full ``_detect_ports`` pass is *additive*: an evenly-spread drop yields the
    blended ``port_activity_drop`` only (no duplicate cargo flag), while a
    type-specific drop the blend misses yields exactly one ``port_cargo_type_drop``.
"""

from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

from freight_radar.detect.detectors import DetectionConfig
from freight_radar.detect.run_detection import (
    CARGO_TYPES,
    _chokepoint_size_flag,
    _detect_ports,
    _dominant_cargo_flag,
)

CFG = DetectionConfig()
RNG = np.random.default_rng(19)


def _arr(flat, n_flat, tail, n_tail):
    """A flat segment then a tail segment, both with mild noise (a level shift)."""
    a = flat + RNG.normal(0, 0.6, n_flat)
    b = tail + RNG.normal(0, 0.5, n_tail)
    return np.concatenate([a, b]).clip(min=0)


def _grp(by_type: dict[str, np.ndarray]) -> pd.DataFrame:
    n = len(next(iter(by_type.values())))
    dates = pd.date_range("2026-01-01", periods=n, freq="D")
    df = pd.DataFrame({"date": dates})
    total = np.zeros(n)
    for t in CARGO_TYPES:
        col = np.rint(by_type[t]).astype(int)
        df[f"portcalls_{t}"] = col
        total += col
    df["portcalls_total"] = total.astype(int)
    return df


# container drops 60 -> 30 on the last 3 days; tanker rises to compensate so the
# BLENDED total stays ~flat — exactly the move a total-only view hides.
def _container_drop_total_flat() -> dict[str, np.ndarray]:
    return {
        "container": _arr(60, 57, 30, 3),
        "tanker": _arr(15, 57, 45, 3),   # +30 compensates the -30 container drop
        "dry_bulk": 10 + RNG.normal(0, 0.5, 60),
        "general_cargo": 8 + RNG.normal(0, 0.5, 60),
        "roro": 5 + RNG.normal(0, 0.4, 60),
    }


def test_helper_fires_on_container_drop_with_flat_total():
    grp = _grp(_container_drop_total_flat())
    flag = _dominant_cargo_flag(
        "port9001", "Testport", grp, CFG, lat=1.0, lon=2.0, econ_weight=1.0
    )
    assert flag is not None, "a dominant-type drop with a flat total should fire"
    assert flag.kind == "port_cargo_type_drop"
    assert flag.metric == "portcalls_container"
    assert "container" in flag.headline.lower()
    assert "container" in flag.brief_md.lower()
    assert "didn't trip the detector" in flag.brief_md
    assert "by type:" in flag.brief_md  # the per-type attribution contrast
    assert flag.pct_change < -25


def test_helper_refuses_when_no_dominant_type():
    """No type clears MIN_DOMINANT_SHARE (~even five-way split) -> None even on a move."""
    even = {t: _arr(20, 57, 8, 3) for t in CARGO_TYPES}  # each ~20% share, all drop
    flag = _dominant_cargo_flag(
        "port9002", "Evenport", _grp(even), CFG, lat=1.0, lon=2.0, econ_weight=1.0
    )
    assert flag is None


# --- integration: the full _detect_ports pass --------------------------------


def _port_db(frames: dict[str, dict[str, np.ndarray]]) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    dims, dailies = [], []
    for i, (portid, by_type) in enumerate(frames.items()):
        dims.append({
            "portid": portid, "portname": portid.upper(), "fullname": portid.upper(),
            "lat": 1.0 + i, "lon": 2.0 + i, "vessel_count_total": 8000 - i * 1000,
        })
        g = _grp(by_type)
        g.insert(0, "portid", portid)
        dailies.append(g)
    dim_df = pd.DataFrame(dims)
    daily_df = pd.concat(dailies, ignore_index=True)
    con.register("_dim", dim_df)
    con.register("_daily", daily_df)
    con.execute("CREATE TABLE dim_port AS SELECT * FROM _dim")
    con.execute("CREATE TABLE fct_port_daily AS SELECT * FROM _daily")
    return con


def test_detect_ports_additive_and_no_double_flag():
    # port A: every type drops ~45% together -> blended catches it (port_activity_drop)
    even_drop = {
        "container": _arr(60, 57, 33, 3), "tanker": _arr(15, 57, 8, 3),
        "dry_bulk": _arr(10, 57, 5, 3), "general_cargo": _arr(8, 57, 4, 3),
        "roro": _arr(5, 57, 3, 3),
    }
    # port B: container-only drop, total flat -> only the cargo detector can see it
    con = _port_db({"portA": even_drop, "portB": _container_drop_total_flat()})
    flags = _detect_ports(con, CFG)
    by_port: dict[str, list] = {}
    for f in flags:
        by_port.setdefault(f.portid, []).append(f)

    assert len(by_port.get("portA", [])) == 1, "exactly one flag per port"
    assert by_port["portA"][0].kind == "port_activity_drop"

    assert len(by_port.get("portB", [])) == 1
    assert by_port["portB"][0].kind == "port_cargo_type_drop"


# --- A3: avg-vessel-size (capacity_total / n_total) detector ------------------


def _dt(values) -> pd.Series:
    idx = pd.date_range("2026-01-01", periods=len(values), freq="D")
    return pd.Series(np.asarray(values, dtype=float), index=idx)


def test_size_flag_fires_on_size_shift_with_flat_count():
    """Transit count flat ~100/day; avg vessel size jumps 25k -> 34k DWT for 3 days.

    Bigger ships, same number of them — a signal the count detector is blind to.
    """
    n = np.concatenate([100 + RNG.normal(0, 1.5, 57), 100 + RNG.normal(0, 1.5, 3)])
    avg = np.concatenate([25000 + RNG.normal(0, 250, 57), 34000 + RNG.normal(0, 250, 3)])
    cap = n * avg  # capacity_total = count * mean size (a flow, not a ceiling)
    flag = _chokepoint_size_flag(
        "chokepoint6", "Gibraltar", _dt(n), _dt(cap), CFG, lat=36.0, lon=-5.3, econ_weight=1.0
    )
    assert flag is not None, "a size shift with a flat count should fire"
    assert flag.kind == "chokepoint_vessel_size_shift"
    assert flag.metric == "avg_vessel_size_dwt"
    assert flag.pct_change > 20
    assert "orthogonal" in flag.brief_md
    assert "capacity utilisation" in flag.brief_md  # the honesty caveat is present


def test_size_flag_handles_zero_traffic_days_without_dividing_by_zero():
    """Most days have zero transits (n=0). The NULLIF/where guard must drop those
    days (no inf/NaN blow-up); with too few valid points the detector returns None."""
    n = np.array([0.0] * 50 + list(100 + RNG.normal(0, 2, 10)))
    cap = np.where(n > 0, n * 25000, 0.0)
    flag = _chokepoint_size_flag(
        "chokepoint9", "Quiet Strait", _dt(n), _dt(cap), CFG, lat=0.0, lon=0.0, econ_weight=1.0
    )
    assert flag is None  # < min_history_days valid points, and crucially: no crash
