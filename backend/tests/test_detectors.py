"""Deterministic unit tests for the detection brain — no network, no DuckDB.

Synthetic pandas series are fed straight into the detector functions so the maths
(STL residual -> rolling z -> flag + severity) is verified in isolation.
"""

from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import pytest

from freight_radar.detect.detectors import (
    DetectionConfig,
    detect_series,
    make_flag_id,
    rolling_zscore,
    severity_score,
)

CFG = DetectionConfig()


def test_rolling_zscore_rejects_degenerate_baseline() -> None:
    # Going wide to ~2065 ports surfaces near-constant/sparse series whose STL residual has a
    # ~1e-15 std — dividing by it once manufactured a z of ~4e15 (and a live flag). A degenerate
    # baseline must yield 0.0 (no statistical basis), never an astronomical z.
    assert rolling_zscore(pd.Series([5.0] * 28 + [9.0]), 28) == 0.0
    assert rolling_zscore(pd.Series([0.0] * 28 + [1.0]), 28) == 0.0
    # a genuinely varied baseline + a real spike still gives a finite, sane z
    rng = np.random.RandomState(0)
    z = rolling_zscore(pd.Series(list(rng.normal(0, 1, 28)) + [5.0]), 28)
    assert 3.0 < abs(z) < 50.0


def _series(values, start="2026-01-01") -> pd.Series:
    idx = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series(np.asarray(values, dtype=float), index=idx)


def test_fires_on_collapse():
    """Flat ~29/day for 60d, then a sharp drop to ~16/day for the last 3 days.

    STL leaves the drop in the residual; the trailing-28d z goes deeply negative and
    a chokepoint_transit_collapse fires with z <= -3 and pct_change ~= -45%.
    """
    rng = np.random.default_rng(7)
    flat = 29 + rng.normal(0, 0.6, 57)        # 57 days near 29
    drop = 16 + rng.normal(0, 0.4, 3)         # last 3 days near 16
    series = _series(np.concatenate([flat, drop]))

    flag = detect_series(
        portid="chokepoint1",
        entity="Suez Canal",
        entity_type="chokepoint",
        metric="n_total",
        values=series,
        as_of=series.index[-1].date(),
        cfg=CFG,
    )

    assert flag is not None, "collapse should have fired a flag"
    assert flag.kind == "chokepoint_transit_collapse"
    assert flag.zscore <= -3.0, f"expected z <= -3, got {flag.zscore}"
    assert flag.pct_change == pytest.approx(-45, abs=6), flag.pct_change
    # the brief must carry the real computed numbers, not placeholders
    assert f"{flag.value:.0f}" in flag.brief_md
    assert f"{flag.zscore:+.1f}" in flag.brief_md


def test_no_fire_on_weekly_seasonality():
    """Clean weekly sinusoid (period 7, weekend dips) + mild noise for 80 days.

    STL(period=7) removes the seasonality, so the residual stays small and NO flag
    fires — this is the false-positive guard the rail depends on.
    """
    rng = np.random.default_rng(11)
    t = np.arange(80)
    weekly = 30 + 8 * np.sin(2 * np.pi * t / 7)   # strong weekend swing
    series = _series(weekly + rng.normal(0, 0.5, 80))

    flag = detect_series(
        portid="chokepoint2",
        entity="Strait of Hormuz",
        entity_type="chokepoint",
        metric="n_total",
        values=series,
        as_of=series.index[-1].date(),
        cfg=CFG,
    )

    assert flag is None, (
        "pure weekly seasonality must not fire a flag "
        f"(got {flag.kind if flag else None}, z={flag.zscore if flag else None})"
    )


def test_severity_monotonic():
    """A bigger-magnitude collapse scores strictly higher severity than a smaller one.

    Checked two ways:
      1. End-to-end: a deep collapse (more sigma) scores >= a shallow one detected
         from real series, and never lower.
      2. The severity formula itself is strictly monotonic in |z| across its
         meaningful (non-saturated) band — magnitude = min(|z|/5, 1) caps at 5 sigma,
         so the strict comparison lives below that cap (which is where real flags,
         z ~ -3..-5, actually land).
    """
    # 1. end-to-end: deeper drop never scores lower than a shallower one.
    rng = np.random.default_rng(3)
    flat = 40 + rng.normal(0, 1.2, 57)
    shallow = _series(np.concatenate([flat, 28 + rng.normal(0, 0.6, 3)]))
    deep = _series(np.concatenate([flat, 10 + rng.normal(0, 0.6, 3)]))
    common = dict(
        portid="chokepoint3", entity="Panama Canal", entity_type="chokepoint",
        metric="n_total", cfg=CFG, econ_weight=1.0,
    )
    f_shallow = detect_series(values=shallow, as_of=shallow.index[-1].date(), **common)
    f_deep = detect_series(values=deep, as_of=deep.index[-1].date(), **common)
    assert f_shallow is not None and f_deep is not None
    assert abs(f_deep.zscore) >= abs(f_shallow.zscore)
    assert f_deep.severity >= f_shallow.severity

    # 2. the formula is STRICTLY monotonic in |z| within the unsaturated band.
    rng2 = np.random.default_rng(0)
    resid = pd.Series(rng2.normal(0, 1, 60), index=pd.date_range("2026-01-01", periods=60, freq="D"))
    sevs = [severity_score(z, resid, CFG, 1.0) for z in (-3.0, -3.5, -4.0, -4.5, -4.9)]
    assert sevs == sorted(sevs) and len(set(sevs)) == len(sevs), sevs


def test_flag_id_stable():
    """Same (kind, portid, ISO week) -> identical flag_id across two calls."""
    as_of = date(2026, 5, 30)
    a = make_flag_id("chokepoint_transit_collapse", "chokepoint1", as_of)
    b = make_flag_id("chokepoint_transit_collapse", "chokepoint1", as_of)
    assert a == b
    assert len(a) == 16
    # a different week (or kind/portid) yields a different id
    other_week = make_flag_id("chokepoint_transit_collapse", "chokepoint1", date(2026, 5, 23))
    assert other_week != a
