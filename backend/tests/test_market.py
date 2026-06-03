"""Market layer honesty invariants (no network — fetch_indicators stubbed)."""

from __future__ import annotations

from datetime import date

import freight_radar.business.market as market


def test_run_market_structure(monkeypatch):
    fake = {
        "brent": {"name": "Brent crude", "unit": "$/bbl", "value": 98.0, "change_pct": 1.0,
                  "as_of": "2026-06-03", "source": "Stooq", "source_url": "x", "stale": False},
        "bunker_vlsfo": {"name": "VLSFO bunker (modeled)", "unit": "$/tonne", "value": 735,
                         "estimate": True, "basis": "modeled_from_brent", "as_of": "2026-06-03",
                         "source": "modeled from Brent", "stale": False},
    }
    monkeypatch.setattr(market, "fetch_indicators", lambda c, t: fake)
    flags = [
        {"flag_id": "f1", "entity": "Strait of Hormuz", "lifecycle": "new"},
        {"flag_id": "f2", "entity": "Taichung", "lifecycle": "new"},
    ]
    p = market.run_market(flags, date(2026, 6, 3))

    # Hormuz is in market_links.yaml; Taichung is not -> honest empty (no item)
    assert "f1" in p["items"] and "f2" not in p["items"]
    assert p["items"]["f1"]["disclaimer"] and "brent" in p["items"]["f1"]["linked"]
    # every indicator with a value carries provenance; estimates are labelled
    for v in p["indicators"].values():
        if v.get("value") is not None:
            assert v.get("source") and v.get("as_of")
    assert p["indicators"]["bunker_vlsfo"]["estimate"] is True


def test_stale_window():
    assert market._stale("2026-05-01", date(2026, 6, 3)) is True
    assert market._stale("2026-06-02", date(2026, 6, 3)) is False
