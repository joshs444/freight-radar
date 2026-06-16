"""Wave 5 detection-depth tests — deterministic, no network, synthetic series.

Covers the four new pieces: the CUSUM+PELT change-point gate, the Cape-of-Good-Hope
reroute divergence detector, the flag lifecycle (new/ongoing/escalated/resolved with
hysteresis), and holiday demand-dip suppression. Every assertion is on
Python-computed numbers from synthetic inputs — nothing hits DuckDB or the network.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date

import numpy as np
import pandas as pd

from freight_radar.detect.cape_reroute import CAPE_ENTITY, CAPE_KIND, detect_cape_reroute
from freight_radar.detect.detectors import DetectionConfig, Flag, detect_series
from freight_radar.detect.holidays import apply_holiday_suppression, in_holiday_window
from freight_radar.detect.lifecycle import apply_lifecycle

CFG = DetectionConfig()
# config loaded from yaml carries holiday windows; the bare dataclass default is
# empty, so tests that exercise holidays supply windows explicitly.
HOLIDAY_CFG = replace(
    CFG,
    holiday_windows=(
        ("Lunar New Year", "02-08", "02-20"),
        ("Christmas / New Year", "12-22", "01-02"),
    ),
)


def _series(values, start="2026-01-01") -> pd.Series:
    idx = pd.date_range(start=start, periods=len(values), freq="D")
    return pd.Series(np.asarray(values, dtype=float), index=idx)


# --- 1. change-point gate suppresses a spurious single-day spike ------------


def test_pelt_gate_suppresses_spurious():
    """A flat noisy series with ONE injected single-day z-spike and no real level
    shift: raw z fires, but the change-point-gated detector does NOT.

    The spike is placed on the last day so the z-scan sees it; because no PELT
    breakpoint sits near an isolated 1-day blip, the gate rejects it. The exact same
    series with the gate OFF must fire — proving the gate is what suppressed it.
    """
    rng = np.random.default_rng(42)
    base = 30 + rng.normal(0, 0.6, 70)
    base[-1] = 30 + 12  # a single-day positive spike (~spike_z worth), no level shift
    series = _series(base)

    common = dict(
        portid="chokepoint6", entity="Strait of Hormuz", entity_type="chokepoint",
        metric="n_total", values=series, as_of=series.index[-1].date(),
    )
    raw = detect_series(cfg=replace(CFG, use_changepoint_gate=False), **common)
    gated = detect_series(cfg=replace(CFG, use_changepoint_gate=True), **common)

    assert raw is not None, "raw z-only detector should fire on the injected spike"
    assert raw.kind == "chokepoint_transit_spike"
    assert gated is None, (
        "the change-point gate must suppress a spurious 1-day spike with no level "
        f"shift (got {gated.kind if gated else None}, z={gated.zscore if gated else None})"
    )


def test_pelt_gate_keeps_real_levelshift():
    """A genuine sustained collapse (a real level shift) still fires WITH the gate.

    Guards the gate against being a blanket mute: a true multi-day step has a PELT
    breakpoint right where the z trips, so it passes the gate.
    """
    rng = np.random.default_rng(7)
    flat = 29 + rng.normal(0, 0.6, 57)
    drop = 16 + rng.normal(0, 0.4, 6)  # sustained 6-day step down
    series = _series(np.concatenate([flat, drop]))
    flag = detect_series(
        portid="chokepoint1", entity="Suez Canal", entity_type="chokepoint",
        metric="n_total", values=series, as_of=series.index[-1].date(),
        cfg=replace(CFG, use_changepoint_gate=True),
    )
    assert flag is not None, "a real sustained collapse must survive the gate"
    assert flag.kind == "chokepoint_transit_collapse"
    assert flag.zscore <= -3.0, flag.zscore


# --- 2. Cape-reroute fires on a real divergence -----------------------------


def test_cape_reroute_fires_on_divergence():
    """Suez+Bab DOWN and Cape UP over the trailing window -> exactly one cape flag,
    with BOTH real magnitudes stated in the brief.
    """
    w = CFG.cape_window
    # prior window: Red Sea ~60/day, Cape ~90/day; latest window: RS ~30, Cape ~120.
    red_sea = _series(np.r_[np.full(w, 60.0), np.full(w, 30.0)])
    cape = _series(np.r_[np.full(w, 90.0), np.full(w, 120.0)])

    flag = detect_cape_reroute(
        red_sea=red_sea, cape=cape, cape_lat=-34.93, cape_lon=20.88,
        as_of=cape.index[-1].date(), cfg=CFG,
    )
    assert flag is not None, "a clear down/up divergence must fire a cape_reroute flag"
    assert flag.kind == CAPE_KIND
    assert flag.entity == CAPE_ENTITY
    assert (flag.lat, flag.lon) == (-34.93, 20.88), "flag must sit at the Cape's geom"
    # real magnitudes: RS -50%, Cape +33%, computed in Python and in the brief.
    assert flag.pct_change == -50.0, flag.pct_change
    assert "50%" in flag.brief_md and "33%" in flag.brief_md, flag.brief_md
    assert flag.severity > 0


def test_cape_reroute_quiet_when_parallel():
    """All three flat/parallel (no divergence) -> no cape flag."""
    w = CFG.cape_window
    flat_rs = _series(np.full(2 * w, 55.0))
    flat_cape = _series(np.full(2 * w, 95.0))
    assert (
        detect_cape_reroute(
            red_sea=flat_rs, cape=flat_cape, cape_lat=-34.9, cape_lon=20.9,
            as_of=flat_cape.index[-1].date(), cfg=CFG,
        )
        is None
    )
    # and a parallel UP move on both sides (no divergence) must also stay quiet.
    up_rs = _series(np.r_[np.full(w, 50.0), np.full(w, 70.0)])
    up_cape = _series(np.r_[np.full(w, 90.0), np.full(w, 120.0)])
    assert (
        detect_cape_reroute(
            red_sea=up_rs, cape=up_cape, cape_lat=-34.9, cape_lon=20.9,
            as_of=up_cape.index[-1].date(), cfg=CFG,
        )
        is None
    ), "both sides up is not a reroute"


# --- 3. lifecycle: new -> ongoing -> escalated, with hysteresis -------------


def _flag(flag_id: str, kind: str, portid: str, severity: int) -> Flag:
    return Flag(
        flag_id=flag_id, kind=kind, entity="E", portid=portid, lat=1.0, lon=2.0,
        severity=severity, headline="h", brief_md="b", metric="n_total",
        value=1.0, baseline=2.0, pct_change=-50.0, zscore=-4.0, as_of="2026-05-25",
    )


def _prior_from(flags: list[Flag]) -> dict[str, dict]:
    """Mimic the fct_flags row dict the lifecycle reader produces."""
    return {
        f.flag_id: {
            "flag_id": f.flag_id, "kind": f.kind, "portid": f.portid,
            "entity": f.entity, "lat": f.lat, "lon": f.lon, "severity": f.severity,
            "headline": f.headline, "brief_md": f.brief_md, "metric": f.metric,
            "value": f.value, "baseline": f.baseline, "pct_change": f.pct_change,
            "zscore": f.zscore, "as_of": f.as_of, "lifecycle": f.lifecycle,
        }
        for f in flags
    }


def test_lifecycle_new_then_ongoing_then_escalated():
    """Drive the lifecycle across runs and assert transitions + hysteresis."""
    fid = "abc123"
    # run 1: unseen -> new
    r1 = apply_lifecycle([_flag(fid, "chokepoint_transit_collapse", "cp1", 50)], {}, CFG)
    assert [f.lifecycle for f in r1] == ["new"]

    # run 2: same flag, tiny severity wobble within the hysteresis band -> ongoing
    prior = _prior_from(r1)
    wobble = _flag(fid, "chokepoint_transit_collapse", "cp1", 50 + CFG.escalate_margin)
    r2 = apply_lifecycle([wobble], prior, CFG)
    assert [f.lifecycle for f in r2] == ["ongoing"], (
        f"+{CFG.escalate_margin} is within the dead-band -> must stay ongoing"
    )

    # run 3: severity jumps past the hysteresis margin -> escalated
    prior = _prior_from(r2)
    jump = _flag(fid, "chokepoint_transit_collapse", "cp1", 50 + CFG.escalate_margin + 25)
    r3 = apply_lifecycle([jump], prior, CFG)
    assert [f.lifecycle for f in r3] == ["escalated"]

    # a severity DROP is never an escalation -> stays ongoing
    prior = _prior_from(r3)
    calmer = _flag(fid, "chokepoint_transit_collapse", "cp1", 40)
    r4 = apply_lifecycle([calmer], prior, CFG)
    assert [f.lifecycle for f in r4] == ["ongoing"]


def test_lifecycle_resolved_tombstone():
    """A previously-active flag whose entity no longer trips is re-emitted ONCE as
    'resolved' with decayed severity, then does not re-resolve next run.
    """
    fid = "dead01"
    prior = _prior_from([_flag(fid, "chokepoint_transit_collapse", "cp9", 80)])
    # current run: cp9 no longer trips (empty current set)
    out = apply_lifecycle([], prior, CFG)
    assert len(out) == 1 and out[0].lifecycle == "resolved"
    assert out[0].severity == int(round(80 * CFG.resolve_decay))
    assert out[0].portid == "cp9"
    # next run: the resolved tombstone is in prior; it must NOT resolve again.
    prior2 = _prior_from(out)
    assert apply_lifecycle([], prior2, CFG) == []


# --- 4. holiday suppression of a benign demand dip --------------------------


def test_holiday_suppresses_benign_dip():
    """The SAME drop is downweighted inside a holiday window and fires outside it."""
    assert in_holiday_window(date(2026, 2, 12), HOLIDAY_CFG) == "Lunar New Year"
    assert in_holiday_window(date(2026, 5, 25), HOLIDAY_CFG) is None
    # year-wrap window check
    assert in_holiday_window(date(2026, 12, 31), HOLIDAY_CFG) == "Christmas / New Year"
    assert in_holiday_window(date(2026, 1, 1), HOLIDAY_CFG) == "Christmas / New Year"

    inside = _flag("h1", "chokepoint_transit_collapse", "cp1", 80)
    inside = replace(inside, as_of="2026-02-12")
    outside = replace(inside, flag_id="h2", as_of="2026-05-25")

    res = apply_holiday_suppression([inside, outside], HOLIDAY_CFG)
    by_id = {f.flag_id: f for f in res}
    assert by_id["h1"].severity == int(round(80 * HOLIDAY_CFG.holiday_downweight)), (
        "a drop inside a holiday window must be downweighted"
    )
    assert "downweighted" in by_id["h1"].brief_md
    assert by_id["h2"].severity == 80, "the same drop outside the window is untouched"

    # a SPIKE inside a holiday window is never suppressed (only drops are seasonal).
    spike = replace(inside, flag_id="h3", kind="chokepoint_transit_spike")
    res2 = apply_holiday_suppression([spike], HOLIDAY_CFG)
    assert res2[0].severity == 80, "spikes are not seasonal -> not suppressed"


# --- 5. ledger-backed prior rows drive the lifecycle (F1 / ADR-0009) ---------


def test_lifecycle_seeds_from_ledger_rows(tmp_path):
    """Prior rows read back from the committed flags ledger drive escalated /
    resolved exactly like the old ``fct_flags`` read did — including a resolved
    tombstone whose brief is rebuilt from the slim ledger numbers (the ledger
    deliberately drops the prose)."""
    from freight_radar import ledger

    def _row(f: Flag) -> dict:
        return {k: getattr(f, k) for k in ledger.FLAG_FIELDS}

    active = _flag("led01", "chokepoint_transit_collapse", "cpL", 50)
    gone = _flag("led02", "chokepoint_transit_spike", "cpM", 80)
    ledger.append_flags("2026-05-25", [_row(active), _row(gone)], tmp_path)
    prior = ledger.prior_flags(tmp_path)
    assert set(prior) == {"led01", "led02"}

    # cpL jumps past the hysteresis margin; cpM no longer trips this run
    hotter = _flag("led01", "chokepoint_transit_collapse", "cpL",
                   50 + CFG.escalate_margin + 15)
    out = apply_lifecycle([hotter], prior, CFG)
    by_port = {f.portid: f for f in out}
    assert by_port["cpL"].lifecycle == "escalated"

    tomb = by_port["cpM"]
    assert tomb.lifecycle == "resolved"
    assert tomb.severity == int(round(80 * CFG.resolve_decay))
    assert tomb.headline.startswith("[Resolved]")
    assert (tomb.lat, tomb.lon) == (1.0, 2.0), "geometry survives the ledger round-trip"
    # the rebuilt brief cites the real recorded numbers, nothing invented
    assert "z = -4" in tomb.brief_md and "_Resolved:" in tomb.brief_md
