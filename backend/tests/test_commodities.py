"""P3 — the commodity SIGNAL: an owned z-score over a cited price, FDR-gated, honest.

The add-a-measured-signal loop in one file: the layer is registered SIGNAL (not context),
sidecar-only (firewall via the registry suite), its copy carries no causal/forecast verb, its
z-score is numerically correct, and a basket enrolls in the FDR gate so it can't manufacture
anomalies. The price stays cited context — we never restate it as ours (G0).
"""

from __future__ import annotations

import inspect
import statistics

import freight_radar.publish as publish
from freight_radar import _http
from freight_radar import commodities as C
from freight_radar.enrich import ENRICHERS
from freight_radar.honesty.lexicon import scan as scan_causal
from freight_radar.registry.layers import EnrichCtx, by_id


def _series(vals: list[float]) -> list[tuple[str, float]]:
    # 13+ ascending monthly (date, value) tuples
    return [(f"20{20 + i // 12:02d}-{i % 12 + 1:02d}-01", v) for i, v in enumerate(vals)]


def test_registered_as_a_signal_sidecar_only() -> None:
    entry = next((e for e in ENRICHERS if e[0] == "commodities"), None)
    assert entry is not None and entry[2] is False  # independent of flags
    assert "commodities" in publish._SIDECARS
    assert by_id("commodities").kind.value == "SIGNAL"  # measured, not context
    assert by_id("commodities").metric  # a SIGNAL declares the scalar it owns


def test_zscore_is_numerically_correct() -> None:
    base = [100, 102, 98, 101, 99, 103, 97, 100, 102, 98, 101, 99]  # 12-month baseline
    m, sd = statistics.mean(base), statistics.stdev(base)
    assert abs(C.zscore_12mo(base + [m]) - 0.0) < 1e-9  # at the mean -> z 0
    assert abs(C.zscore_12mo(base + [m + 3 * sd]) - 3.0) < 1e-9  # +3 sd -> z 3
    assert C.zscore_12mo([10] * 12) is None  # <13 values -> no baseline
    assert C.zscore_12mo([10] * 13) is None  # flat baseline (sd 0) -> undefined, never a fake 0


def test_basket_enrolls_in_fdr() -> None:
    series = {
        "POILBREUSDM": _series([100, 101, 99, 100, 102, 98, 100, 101, 99, 100, 101, 99, 200]),  # spike
        "PCOPPUSDM": _series([100, 101, 99, 100, 102, 98, 100, 101, 99, 100, 101, 99, 100.5]),  # calm
    }
    sig = C.compute_signal(series, q=0.10)
    assert sig["counts"]["tested"] == 2
    by_name = {r["id"]: r for r in sig["items"]}
    assert by_name["POILBREUSDM"]["fdr_significant"] is True  # the genuine anomaly survives
    assert by_name["PCOPPUSDM"]["fdr_significant"] is False  # the calm one is not flagged


def test_parse_series_drops_missing() -> None:
    text = "observation_date,X\n2025-01-01,100.5\n2025-02-01,.\n2025-03-01,102.0\n"
    assert C.parse_series(text) == [("2025-01-01", 100.5), ("2025-03-01", 102.0)]


def test_copy_carries_no_causal_or_forecast_verb() -> None:
    hits = scan_causal(inspect.getsource(C))
    assert not hits, f"causal/forecast verb in commodities copy: {hits}"


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
    receipt = C.run(ctx)
    assert "error" in receipt  # degraded, never crashed publish
    assert not (tmp_path / "commodities.json").exists()
