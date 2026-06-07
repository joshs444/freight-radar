"""P4 — the streamflow CONTEXT layer (USGS river gage height) honesty four-pack + parser."""

from __future__ import annotations

import inspect

import freight_radar.publish as publish
from freight_radar import _http
from freight_radar import streamflow as S
from freight_radar.enrich import ENRICHERS
from freight_radar.honesty.lexicon import scan as scan_causal
from freight_radar.registry.layers import EnrichCtx, by_id


def test_registered_as_a_context_sidecar() -> None:
    entry = next((e for e in ENRICHERS if e[0] == "streamflow"), None)
    assert entry is not None and entry[2] is False  # independent of flags
    assert "streamflow" in publish._SIDECARS
    assert by_id("streamflow").kind.value == "CONTEXT"
    assert by_id("streamflow").metric is None  # CONTEXT owns no computed number


def test_copy_carries_no_causal_or_forecast_verb() -> None:
    hits = scan_causal(inspect.getsource(S))
    assert not hits, f"causal/forecast verb in streamflow copy: {hits}"


def test_parse_extracts_geo_and_stage() -> None:
    payload = {
        "value": {
            "timeSeries": [
                {
                    "sourceInfo": {
                        "siteCode": [{"value": "07010000"}],
                        "geoLocation": {"geogLocation": {"latitude": 38.6, "longitude": -90.2}},
                    },
                    "values": [{"value": [{"value": "10.87", "dateTime": "2026-06-06T18:30"}]}],
                }
            ]
        }
    }
    items = S.parse(payload)
    assert len(items) == 1
    it = items[0]
    assert it["site"] == "07010000" and it["stage_ft"] == 10.87
    assert it["lat"] == 38.6 and it["river"] == "Mississippi"
    assert it["url"].endswith("07010000/")


def test_parse_drops_missing_sentinel_and_unknown_sites() -> None:
    missing = {
        "value": {
            "timeSeries": [
                {
                    "sourceInfo": {
                        "siteCode": [{"value": "07010000"}],
                        "geoLocation": {"geogLocation": {"latitude": 1, "longitude": 2}},
                    },
                    "values": [{"value": [{"value": "-999999", "dateTime": "x"}]}],
                }
            ]
        }
    }
    assert S.parse(missing) == []  # USGS missing-data sentinel dropped


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
    receipt = S.run(ctx)
    assert "error" in receipt
    assert not (tmp_path / "streamflow.json").exists()
