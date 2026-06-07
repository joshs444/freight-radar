"""P4 — the marine wave-height CONTEXT layer honesty four-pack + parser."""

from __future__ import annotations

import inspect

import freight_radar.publish as publish
from freight_radar import _http
from freight_radar import marine as M
from freight_radar.enrich import ENRICHERS
from freight_radar.honesty.lexicon import scan as scan_causal
from freight_radar.registry.layers import EnrichCtx, by_id


def test_registered_as_a_context_sidecar() -> None:
    entry = next((e for e in ENRICHERS if e[0] == "marine"), None)
    assert entry is not None and entry[2] is False
    assert "marine" in publish._SIDECARS
    assert by_id("marine").kind.value == "CONTEXT"
    assert by_id("marine").metric is None


def test_copy_carries_no_causal_or_forecast_verb() -> None:
    hits = scan_causal(inspect.getsource(M))
    assert not hits, f"causal/forecast verb in marine copy: {hits}"


def test_parse_skips_inland_nulls_and_sorts_by_wave() -> None:
    recs = [
        {"current": {"wave_height": 1.2, "wave_period": 6, "time": "t"}},  # Hormuz
        {"current": {"wave_height": None}},  # Malacca -> dropped (no open-water wave)
        {"current": {"wave_height": 3.5, "wave_period": 8, "time": "t"}},  # Singapore
    ]
    items = M.parse(recs)
    assert len(items) == 2
    assert items[0]["wave_height_m"] == 3.5 and items[0]["name"] == "Singapore Strait"
    assert items[1]["name"] == "Strait of Hormuz"


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
    assert "error" in M.run(ctx)
    assert not (tmp_path / "marine.json").exists()
