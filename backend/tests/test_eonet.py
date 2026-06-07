"""P4 — the EONET natural-event CONTEXT layer honesty four-pack + parser."""

from __future__ import annotations

import inspect

import freight_radar.publish as publish
from freight_radar import _http
from freight_radar import eonet as E
from freight_radar.enrich import ENRICHERS
from freight_radar.honesty.lexicon import scan as scan_causal
from freight_radar.registry.layers import EnrichCtx, by_id


def test_registered_as_a_context_sidecar() -> None:
    entry = next((e for e in ENRICHERS if e[0] == "eonet"), None)
    assert entry is not None and entry[2] is False
    assert "eonet" in publish._SIDECARS
    assert by_id("eonet").kind.value == "CONTEXT"
    assert by_id("eonet").metric is None


def test_copy_carries_no_causal_or_forecast_verb() -> None:
    hits = scan_causal(inspect.getsource(E))
    assert not hits, f"causal/forecast verb in eonet copy: {hits}"


def test_parse_takes_latest_point_and_skips_polygons() -> None:
    events = [
        {
            "id": "x",
            "title": "Wildfire A",
            "link": "u",
            "categories": [{"title": "Wildfires"}],
            "geometry": [
                {"type": "Point", "coordinates": [-119.0, 37.0], "date": "2026-06-05T00:00:00Z"},
                {"type": "Point", "coordinates": [-120.0, 38.0], "date": "2026-06-06T18:00:00Z"},
            ],
        },
        {
            "id": "poly",
            "title": "P",
            "categories": [{"title": "X"}],
            "geometry": [{"type": "Polygon", "coordinates": [[[1, 2]]], "date": "x"}],
        },
    ]
    items = E.parse(events)
    assert len(items) == 1  # the polygon-only event is skipped
    assert items[0]["category"] == "Wildfires"
    assert items[0]["lat"] == 38.0 and items[0]["lon"] == -120.0  # latest geometry wins


def test_degrades_to_absent_offline(tmp_path, monkeypatch) -> None:
    def boom(*_a, **_k):
        raise RuntimeError("network blocked")

    monkeypatch.setattr(_http, "client", boom)
    monkeypatch.setattr(_http, "get", boom)
    ctx = EnrichCtx(
        db_path=tmp_path / "x",
        out_dir=tmp_path,
        flags_path=tmp_path / "f.json",
        as_of="2026-05-31",
        today="2026-06-06",
    )
    assert "error" in E.run(ctx)
    assert not (tmp_path / "eonet.json").exists()
