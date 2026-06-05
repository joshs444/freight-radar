"""History payload tests — build_payload over a synthetic daily frame (no network).

Pins the contract the frontend History view relies on: weekly downsampling, the stress
series wired to the live engine, JSON-safe event dates, and a visible stress lift when a
chokepoint's throughput collapses."""

from __future__ import annotations

import datetime as dt

import pandas as pd

from freight_radar import history


def _frame() -> pd.DataFrame:
    """Two chokepoints over ~40 weeks; one collapses to a fraction partway through."""
    rows = []
    base = dt.date(2020, 1, 1)
    for i in range(280):  # 40 weeks
        d = (base + dt.timedelta(days=i)).isoformat()
        rows.append({"portid": "chokepoint1", "name": "Calm Strait", "lat": 1.0, "lon": 2.0,
                     "date": d, "v": 100.0})
        # chokepoint2 collapses to 10% after day 140 (a sustained shock)
        v = 80.0 if i < 140 else 8.0
        rows.append({"portid": "chokepoint2", "name": "Shock Strait", "lat": 3.0, "lon": 4.0,
                     "date": d, "v": v})
    return pd.DataFrame(rows)


def test_build_payload_shape_and_events():
    payload = history.build_payload(_frame(), today="2020-10-07")
    assert payload["resolution"] == "weekly"
    assert payload["dates"] and len(payload["dates"]) == len(payload["stress"])
    assert {c["portid"] for c in payload["chokepoints"]} == {"chokepoint1", "chokepoint2"}
    for c in payload["chokepoints"]:
        assert len(c["values"]) == len(payload["dates"])
        assert "normal" in c
    # curated events load + their dates are JSON-safe strings (not date objects)
    assert payload["events"], "expected curated events"
    for e in payload["events"]:
        assert isinstance(e["date"], str)


def test_stress_lifts_on_a_sustained_collapse():
    payload = history.build_payload(_frame(), today="2020-10-07")
    st = payload["stress"]
    # the back half (after the collapse) should read more stressed than the calm start
    assert max(st[20:]) > min(st[:10]) + 5
