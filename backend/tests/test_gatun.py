"""Tests for the Panama Gatun enricher's CSV parsing + draft logic (no network)."""

from __future__ import annotations

from freight_radar import gatun as G

HISTORY = "DATE_LOG,GATUN_LAKE_LEVEL(FEET)\n1965-01-01,86.49\n2026-06-01,85.19\n2026-06-02,85.20\n"
PROJECTION = (
    "The estimated maximum drafts ... reference purposes only.\n"
    "The official maximum ... Advisories to Shipping.\n"
    "projected_date,projected_gatun_water_level,surcharge_pcent,max_neopanamax_draft_ft,max_panamax_draft_ft\n"
    "06/10/2026, 85.2, 0.24, 50.0, 39.5\n"
    "06/20/2026, 84.8, 0.30, 49.5, 39.5\n"
)


def test_parse_history_skips_header_and_typed():
    rows = G._parse_history(HISTORY)
    assert rows[0] == ("1965-01-01", 86.49)
    assert rows[-1] == ("2026-06-02", 85.20)
    assert all(isinstance(v, float) for _, v in rows)


def test_parse_projection_skips_disclaimer_preamble():
    proj = G._parse_projection(PROJECTION)
    assert len(proj) == 2
    assert proj[0]["neopanamax_draft_ft"] == 50.0
    assert proj[1]["surcharge_pct"] == 0.30
    assert proj[1]["neopanamax_draft_ft"] == 49.5


def test_pctile_of():
    assert G._pctile_of(50, [10, 20, 30, 40, 50]) == 100.0
    assert G._pctile_of(10, [10, 20, 30, 40, 50]) == 20.0


def test_build_via_injected_client(monkeypatch):
    # a fake httpx.Client whose .get returns our fixtures by URL
    class _Resp:
        def __init__(self, text): self.text = text
        def raise_for_status(self): pass

    class _Client:
        def get(self, url):
            return _Resp(HISTORY if "History" in url else PROJECTION)

    out = G.build(client=_Client())
    assert out["available"] is True
    assert out["current_level_ft"] == 85.2
    assert out["min_projected_neopanamax_draft_ft"] == 49.5
    assert out["draft_restricted"] is True          # 49.5 < 50.0 normal
    assert out["portid"] == "chokepoint2"
