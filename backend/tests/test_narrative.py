"""Tests for the narrative layer: stress index, event ledger, weekly brief.

The emphasis is on the honesty properties that matter for a portfolio piece:
  - a calm system reads calm; a sustained single-strait collapse reads "high"
    (the depth term isn't averaged away) and KEEPS contributing even after a
    rolling baseline would have adapted (the Hormuz lesson, encoded as a test);
  - the event ledger diffs correctly across runs (appeared/escalated/resolved);
  - the brief is internally consistent — it never states a number the stress
    index would contradict (the stale-flag-vs-current-level trap).
"""

from __future__ import annotations

import json
from datetime import date

from freight_radar.narrative import stress as S
from freight_radar.narrative import events as E
from freight_radar.narrative import brief as B


def _ts(series: dict[str, list[float]], n: int) -> dict:
    """Build a minimal timeseries payload from {name: values}."""
    dates = [f"2026-01-{d:02d}" for d in range(1, n + 1)] if n <= 28 else \
        [f"2026-{1 + i // 28:02d}-{1 + i % 28:02d}" for i in range(n)]
    chokes = []
    for i, (name, vals) in enumerate(series.items()):
        chokes.append({"portid": f"cp{i}", "name": name, "lat": 0.0, "lon": 0.0, "values": vals})
    return {"dates": dates, "chokepoints": chokes}


# --- stress index ----------------------------------------------------------
def test_calm_system_reads_calm():
    n = 90
    ts = _ts({f"S{i}": [100] * n for i in range(10)}, n)
    out = S.compute(ts)
    assert out["available"]
    assert 0 <= out["index"] <= 5
    assert out["label"] == "calm"


def test_index_bounded_0_100():
    n = 90
    # one chokepoint at 0, rest normal — index must stay in-range
    ts = _ts({"Dead": [0] * n, **{f"S{i}": [100] * n for i in range(5)}}, n)
    out = S.compute(ts)
    assert 0 <= out["index"] <= 100
    assert 0 <= out["breadth"] <= 100
    assert 0 <= out["depth"] <= 100


def test_single_strait_collapse_not_averaged_away():
    """A lone major-strait collapse must register as 'high' via the depth term,
    even though every other lane flows normally (the anti-wash-out property)."""
    n = 90
    series = {f"Normal{i}": [200] * n for i in range(20)}
    series["BigStrait"] = [80] * 60 + [6] * 30     # collapses and STAYS down
    ts = _ts(series, n)
    out = S.compute(ts)
    # breadth is small (1 of 21 disrupted) but depth is near-max → index "high"
    assert out["depth"] >= 80
    assert out["index"] >= 35
    assert out["label"] in ("high", "severe")


def test_sustained_shift_still_stressed_at_end():
    """Deviation is measured vs the NORMAL (80th pct of window), not a trailing
    mean — so a level shift the rolling baseline would have adapted to still reads
    as stressed at the latest day. This is the Strait-of-Hormuz blind-spot fix."""
    n = 120
    series = {f"N{i}": [150] * n for i in range(10)}
    series["Shifted"] = [100] * 30 + [8] * 90       # 90 days at the new low level
    ts = _ts(series, n)
    out = S.compute(ts)
    shifted = next(c for c in out["contributors"] if c["name"] == "Shifted")
    assert shifted["stress"] >= 0.7                 # still highly stressed at day 120
    assert shifted["pct_vs_normal"] < -50


def test_contributions_are_breadth_decomposition():
    n = 90
    ts = _ts({"A": [100] * 60 + [10] * 30, "B": [100] * n}, n)
    out = S.compute(ts)
    # sum of contributions ≈ 100 * breadth (the weighted-mean component)
    total = sum(c["contribution"] for c in out["contributors"])
    assert abs(total - out["breadth"]) < 0.5


# --- event ledger ----------------------------------------------------------
def _fp(flags):
    return E._fingerprint(flags)


def test_first_run_all_appeared_then_stable():
    flags = [{"flag_id": "a", "entity": "X", "kind": "k", "severity": 50, "as_of": "2026-05-01", "lifecycle": "ongoing"},
             {"flag_id": "b", "entity": "Y", "kind": "k", "severity": 30, "as_of": "2026-05-01", "lifecycle": "ongoing"}]
    curr = _fp(flags)
    ev1 = E.diff({}, curr, "2026-05-01", 0)
    assert {e["type"] for e in ev1} == {"appeared"}
    assert len(ev1) == 2
    # identical next run → no events
    ev2 = E.diff(curr, curr, "2026-05-08", 2)
    assert ev2 == []


def test_escalation_and_resolution():
    prev = _fp([{"flag_id": "a", "entity": "X", "kind": "k", "severity": 40, "as_of": "2026-05-01", "lifecycle": "ongoing"},
                {"flag_id": "b", "entity": "Y", "kind": "k", "severity": 30, "as_of": "2026-05-01", "lifecycle": "ongoing"}])
    curr = _fp([{"flag_id": "a", "entity": "X", "kind": "k", "severity": 55, "as_of": "2026-05-08", "lifecycle": "ongoing"}])
    ev = E.diff(prev, curr, "2026-05-08", 5)
    kinds = {e["type"] for e in ev}
    assert "escalated" in kinds        # a: 40 -> 55 (>= +10)
    assert "resolved" in kinds         # b: gone
    esc = next(e for e in ev if e["type"] == "escalated")
    assert esc["from_severity"] == 40 and esc["severity"] == 55


# --- weekly brief ----------------------------------------------------------
def _write(tmp, name, obj):
    (tmp / name).write_text(json.dumps(obj))


def test_brief_bullets_all_cited(tmp_path):
    _write(tmp_path, "flags.json", [
        {"flag_id": "h", "entity": "Strait of Hormuz", "kind": "chokepoint_persistent_collapse",
         "severity": 83, "pct_change": -92.4, "as_of": "2026-03-01", "lifecycle": "ongoing", "portid": "cp6"}])
    _write(tmp_path, "stress.json", {
        "available": True, "index": 41.6, "label": "high", "as_of": "2026-05-31",
        "wow_delta": 1.5, "wow_direction": "up", "chokepoints_total": 28, "chokepoints_disrupted": 3,
        "contributors": [{"portid": "cp6", "name": "Strait of Hormuz", "now": 10.0, "normal": 80.4, "pct_vs_normal": -87.6}]})
    _write(tmp_path, "market.json", {"indicators": {"brent": {"value": 96.7, "change_pct": -0.6, "change_basis": "intraday", "name": "Brent crude", "unit": "$/bbl"}}, "items": {"h": {}}})
    _write(tmp_path, "exposure.json", {"exposed_value_usd": 314000000, "carrying_cost_of_delay_usd": {"low": 404384, "expected": 781506, "high": 1269040}, "active_disruptions_hitting_you": 5})
    out = B.build(tmp_path, date(2026, 6, 3))
    assert out["bullets"]
    for b in out["bullets"]:
        assert b.get("cites"), f"uncited bullet: {b}"
    # the stress bullet must echo the real index, not a recomputed one
    sb = next(b for b in out["bullets"] if b["kind"] == "stress")
    assert "41.6" in sb["text"]


def test_brief_movers_never_contradict_stress(tmp_path):
    """The movers bullet must reflect the CURRENT level from the stress index, not a
    flag's frozen detection-day pct_change (which may have since reverted)."""
    _write(tmp_path, "flags.json", [
        {"flag_id": "k", "entity": "Kerch Strait", "kind": "chokepoint_transit_spike",
         "severity": 29, "pct_change": 579.2, "as_of": "2026-05-18", "lifecycle": "ongoing", "portid": "cp28"},
        {"flag_id": "h", "entity": "Hormuz", "kind": "chokepoint_persistent_collapse",
         "severity": 83, "pct_change": -92.4, "as_of": "2026-03-01", "lifecycle": "ongoing", "portid": "cp6"}])
    _write(tmp_path, "stress.json", {
        "available": True, "index": 41.6, "label": "high", "as_of": "2026-05-31",
        "wow_delta": 1.5, "wow_direction": "up", "chokepoints_total": 28, "chokepoints_disrupted": 3,
        "contributors": [
            {"portid": "cp6", "name": "Hormuz", "now": 10.0, "normal": 80.4, "pct_vs_normal": -87.6},
            {"portid": "cp28", "name": "Kerch Strait", "now": 6.0, "normal": 17.0, "pct_vs_normal": -64.7}]})
    out = B.build(tmp_path, date(2026, 6, 3))
    movers = next((b for b in out["bullets"] if b["kind"] == "movers"), None)
    assert movers is not None
    assert "579" not in movers["text"]          # the stale spike must NOT appear
    assert "65% below" in movers["text"]         # the current level does
    assert movers["cites"] == ["stress.json"]
