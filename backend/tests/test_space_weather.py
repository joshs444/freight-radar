"""P4 — the space-weather CONTEXT layer (NOAA SWPC) honesty four-pack + compute."""

from __future__ import annotations

import inspect

import freight_radar.publish as publish
from freight_radar import _http
from freight_radar import space_weather as SW
from freight_radar.enrich import ENRICHERS
from freight_radar.honesty.lexicon import scan as scan_causal
from freight_radar.registry.layers import EnrichCtx, by_id


def test_registered_as_a_context_sidecar() -> None:
    entry = next((e for e in ENRICHERS if e[0] == "space_weather"), None)
    assert entry is not None and entry[2] is False
    assert "space_weather" in publish._SIDECARS
    assert by_id("space_weather").kind.value == "CONTEXT"
    assert by_id("space_weather").metric is None


def test_copy_carries_no_causal_or_forecast_verb() -> None:
    hits = scan_causal(inspect.getsource(SW))
    assert not hits, f"causal/forecast verb in space_weather copy: {hits}"


def test_compute_builds_observed_snapshot() -> None:
    kp = [
        {"time_tag": "2026-06-06T00:00:00", "Kp": 2.0},
        {"time_tag": "2026-06-06T03:00:00", "Kp": 5.33},
    ]
    scales = {
        "0": {
            "R": {"Scale": "1", "Text": "minor"},
            "S": {"Scale": "0", "Text": "none"},
            "G": {"Scale": "2", "Text": "moderate"},
        }
    }
    snap = SW.compute(kp, scales)
    assert snap is not None
    assert snap["kp_now"] == 5.33 and snap["kp_max_48h"] == 5.33
    assert snap["geomagnetic_storm"] == {"scale": "G2", "label": "moderate"}
    assert snap["scales"]["R_radio_blackout"]["level"] == "1"
    assert len(snap["items"]) == 2


def test_compute_returns_none_without_kp() -> None:
    assert SW.compute([], {}) is None
    assert SW.compute([{"time_tag": "x"}], {}) is None  # row carries no Kp


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
    assert "error" in SW.run(ctx)
    assert not (tmp_path / "space_weather.json").exists()
