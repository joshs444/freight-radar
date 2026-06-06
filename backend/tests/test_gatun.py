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


def test_published_min_draft_always_traces_to_a_visible_projection_row():
    """Regression: the restricted min-draft must appear in a PUBLISHED projection row and
    the projection must be chronological — even when ACP lists the min row last / unsorted
    past the old 12-row cut (the bug where min=49.5 contradicted 12 visible 50.0 rows)."""
    rows = "".join(f"06/{d:02d}/2026, 85.0, 0.24, 50.0, 39.5\n" for d in range(2, 14))  # 12x 50.0
    proj_text = (
        "preamble disclaimer line\n"
        "projected_date,projected_gatun_water_level,surcharge_pcent,max_neopanamax_draft_ft,max_panamax_draft_ft\n"
        + rows
        + "06/25/2026, 84.0, 0.40, 49.0, 39.0\n"  # the genuine min, LAST in the file
    )

    class _Resp:
        def __init__(self, text): self.text = text
        def raise_for_status(self): pass

    class _Client:
        def get(self, url): return _Resp(HISTORY if "History" in url else proj_text)

    out = G.build(client=_Client())
    assert out["min_projected_neopanamax_draft_ft"] == 49.0
    assert out["draft_restricted"] is True
    drafts = [p["neopanamax_draft_ft"] for p in out["projection"]]
    assert 49.0 in drafts, "the published min draft must be traceable to a visible row"
    assert out["projection"] == sorted(out["projection"], key=G._proj_date), "must be chronological"
