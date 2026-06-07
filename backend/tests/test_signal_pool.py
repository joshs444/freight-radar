"""Pooled FDR — one Benjamini-Hochberg family across all signal silos, and it is STRICTER
than per-silo FDR (the correctness point: a weak anomaly that clears a tiny family must not
clear the whole signal universe)."""

from __future__ import annotations

import json
from pathlib import Path

from freight_radar.multiplicity import control_z
from freight_radar.signal_pool import pool_signals, write


def _sig(d: Path, stem: str, items: list[dict]) -> None:
    (d / f"{stem}.json").write_text(json.dumps({"items": items}))


def test_pooling_is_stricter_than_per_silo(tmp_path) -> None:
    # commodities: one lone z=2.2 — significant ALONE (silo m=1)
    _sig(tmp_path, "commodities", [{"id": "X", "name": "X", "our_zscore": 2.2}])
    # macro: ten noise series — they enlarge the family the 2.2 must now survive
    _sig(tmp_path, "macro", [{"id": f"N{i}", "name": f"N{i}", "our_zscore": 0.2} for i in range(10)])

    # the silo verdict: z=2.2 alone clears BH at q=0.10
    silo_keep, _ = control_z([2.2], q=0.10)
    assert silo_keep == [True]

    pooled = pool_signals(tmp_path, q=0.10)
    assert pooled["counts"]["tested"] == 11  # one m over the WHOLE universe
    x = next(r for r in pooled["items"] if r["id"] == "X")
    assert x["fdr_significant"] is False, "pooling must be stricter — 2.2 fails against m=11"


def test_pool_over_real_committed_signals_is_coherent() -> None:
    data = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"
    pooled = pool_signals(data)
    items = pooled["items"]
    assert items, "expected the committed signal families to pool"
    assert pooled["counts"]["tested"] == len(items)  # every signal is one test in the pool
    # pooling never invents significance beyond the per-family silos combined (over ALL families)
    from freight_radar.signal_pool import SIGNAL_STEMS

    silo_sig = 0
    for stem in SIGNAL_STEMS:
        p = data / f"{stem}.json"
        if p.exists():
            silo_sig += sum(1 for it in json.loads(p.read_text())["items"] if it.get("fdr_significant"))
    assert pooled["counts"]["significant"] <= silo_sig, "pooled significance is stricter-or-equal"
    assert pooled["counts"]["expected_false"] == round(0.10 * pooled["counts"]["significant"], 3)


def test_write_skips_when_no_signal_family_present(tmp_path) -> None:
    # the hermetic golden run (network blocked) has no signal sidecars — nothing to pool
    assert write(tmp_path) is None
    assert not (tmp_path / "signals_fdr.json").exists()
