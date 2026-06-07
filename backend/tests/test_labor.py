"""P3 — the labor SIGNAL honesty four-pack + FDR."""

from __future__ import annotations

import inspect

import freight_radar.publish as publish
from freight_radar import _http
from freight_radar import labor as L
from freight_radar.enrich import ENRICHERS
from freight_radar.honesty.lexicon import scan as scan_causal
from freight_radar.registry.layers import EnrichCtx, by_id


def _series(vals: list[float]) -> list[tuple[str, float]]:
    return [(f"20{20 + i // 12:02d}-{i % 12 + 1:02d}-01", v) for i, v in enumerate(vals)]


def test_registered_as_a_signal_sidecar() -> None:
    entry = next((e for e in ENRICHERS if e[0] == "labor"), None)
    assert entry is not None and entry[2] is False
    assert "labor" in publish._SIDECARS
    assert by_id("labor").kind.value == "SIGNAL"
    assert by_id("labor").metric


def test_copy_carries_no_causal_or_forecast_verb() -> None:
    hits = scan_causal(inspect.getsource(L))
    assert not hits, f"causal/forecast verb in labor copy: {hits}"


def test_basket_enrolls_in_fdr() -> None:
    series = {
        "CEU4348400001": _series([100, 101, 99, 100, 102, 98, 100, 101, 99, 100, 101, 99, 200]),
        "MANEMP": _series([100, 101, 99, 100, 102, 98, 100, 101, 99, 100, 101, 99, 100.5]),
    }
    sig = L.compute_signal(series, q=0.10)
    assert sig["counts"]["tested"] == 2
    by = {r["id"]: r for r in sig["items"]}
    assert by["CEU4348400001"]["fdr_significant"] is True
    assert by["MANEMP"]["fdr_significant"] is False


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
    assert "error" in L.run(ctx)
    assert not (tmp_path / "labor.json").exists()
