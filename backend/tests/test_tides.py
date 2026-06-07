"""P4 — the tides (NOAA CO-OPS water level) CONTEXT layer honesty four-pack + parser."""

from __future__ import annotations

import inspect

import freight_radar.publish as publish
from freight_radar import _http
from freight_radar import tides as T
from freight_radar.enrich import ENRICHERS
from freight_radar.honesty.lexicon import scan as scan_causal
from freight_radar.registry.layers import EnrichCtx, by_id


def test_registered_as_a_context_sidecar() -> None:
    entry = next((e for e in ENRICHERS if e[0] == "tides"), None)
    assert entry is not None and entry[2] is False
    assert "tides" in publish._SIDECARS
    assert by_id("tides").kind.value == "CONTEXT"
    assert by_id("tides").metric is None


def test_copy_carries_no_causal_or_forecast_verb() -> None:
    hits = scan_causal(inspect.getsource(T))
    assert not hits, f"causal/forecast verb in tides copy: {hits}"


def test_level_parses_and_handles_missing() -> None:
    assert T._level({"data": [{"v": "3.68"}]}) == 3.68
    assert T._level({"data": []}) is None
    assert T._level({"data": [{"v": None}]}) is None
    assert T._level({}) is None


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
    assert "error" in T.run(ctx)
    assert not (tmp_path / "tides.json").exists()
