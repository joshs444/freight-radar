"""The DERIVED reasoner's fail-closed gate + the reasoner itself.

The committed briefing must pass the full gate (validate + attribution + abstention +
provenance); the gate must FIRE on an unentailed number, a causal claim, and a bad cite; and
the reasoner must produce a gate-clean briefing from the live store. This is the eval any
LLM-authored briefing would have to pass to ship — a hallucinated number fails here, in CI.
(Today's reasoner is deterministic templates; the gate doesn't care who authored the claim.)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from freight_radar.derived import reason
from freight_radar.derived.gate import attribution_violations, gate_briefing
from freight_radar.registry.layers import REGISTRY

DATA = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"
VALID = {d.id for d in REGISTRY}
BRIEFING = DATA / "ai_briefing.json"


def test_committed_briefing_passes_the_whole_gate() -> None:
    if not BRIEFING.exists():
        # A legitimately demoted briefing (the gate tripped in the last refresh) is allowed
        # — but ONLY with its receipt. A missing file with no demotion record is a real bug,
        # and reading it blindly here used to crash CI for every push after a demotion.
        dem = DATA / "demotions.json"
        recs = json.loads(dem.read_text()).get("demoted", []) if dem.exists() else []
        assert any(d.get("stem") == "ai_briefing" for d in recs), \
            "ai_briefing.json missing with no demotion receipt"
        pytest.skip("ai_briefing demoted to dark (receipt present) — nothing to gate")
    b = json.loads(BRIEFING.read_text())
    assert gate_briefing(b, VALID, out_dir=DATA) == {}, gate_briefing(b, VALID, out_dir=DATA)


def test_attribution_fires_on_an_unentailed_number() -> None:
    # a fabricated value the cited layer does not contain must be caught (the hallucination gate).
    # Use a value far outside every range stress.json holds (index/stress 0-100, vessel counts
    # ~hundreds): the current oracle is a number-SET match with a 0.1% tolerance, so a
    # plausible in-range fake (e.g. 99.9) can be spuriously "entailed" by a real neighbor like
    # 100.0 — that looseness is what F2's value-at-path oracle (H5-C) replaces; until then the
    # sentinel must be unambiguously out of range so the assertion is data-independent.
    bad = {
        "tier": "DERIVED",
        "agent_model": "x",
        "claims": [{"text": "The stress index reads 12345.6.", "cites": ["stress"]}],
    }
    assert attribution_violations(bad, out_dir=DATA), "12345.6 is not in stress.json — must fail"
    assert gate_briefing(bad, VALID, out_dir=DATA).get("attribution")


def test_gate_is_a_fail_closed_conjunction() -> None:
    # a causal claim trips the language firewall (inside validate); a bad cite trips validate
    causal = {
        "tier": "DERIVED",
        "agent_model": "x",
        "claims": [{"text": "the drop was caused by the quake", "cites": ["stress"]}],
    }
    assert gate_briefing(causal, VALID, out_dir=DATA).get("validate")
    badcite = {
        "tier": "DERIVED",
        "agent_model": "x",
        "claims": [{"text": "x", "cites": ["not_a_layer"]}],
    }
    assert gate_briefing(badcite, VALID, out_dir=DATA).get("validate")


def test_the_reasoner_produces_a_gate_clean_briefing() -> None:
    b = reason.build(DATA)
    assert b["tier"] == "DERIVED" and b["metric"] is None
    assert len(b["claims"]) >= 4
    assert gate_briefing(b, VALID, out_dir=DATA) == {}


def test_the_reasoner_refuses_to_write_an_ungated_briefing(tmp_path, monkeypatch) -> None:
    # force the build to emit an unentailed claim -> write() must raise, never ship it
    monkeypatch.setattr(
        reason,
        "build",
        lambda out_dir: {
            "tier": "DERIVED",
            "metric": None,
            "agent_model": "x",
            "claims": [{"text": "stress reads 1234.5", "cites": ["stress"]}],
        },
    )
    with pytest.raises(reason.DerivedGateBlocked):
        reason.write(DATA)


def test_a_gate_block_demotes_the_layer_never_the_refresh(tmp_path, monkeypatch) -> None:
    # the briefing is OPTIONAL garnish: a gate trip must take the LAYER dark — stale
    # ai_briefing.json removed, a demotions.json receipt MERGED (not clobbered) — and let
    # the refresh proceed (main() exits 0). write() raising stays the fail-closed contract.
    (tmp_path / "ai_briefing.json").write_text("{}")
    (tmp_path / "demotions.json").write_text(
        json.dumps({"note": "n", "demoted": [{"stem": "news", "violations": ["x"]}]})
    )

    def blocked(out_dir):
        raise reason.DerivedGateBlocked("forced for the test")

    monkeypatch.setattr(reason, "write", blocked)
    assert reason.main([str(tmp_path)]) == 0
    assert not (tmp_path / "ai_briefing.json").exists()
    rec = json.loads((tmp_path / "demotions.json").read_text())
    assert [d["stem"] for d in rec["demoted"]] == ["news", "ai_briefing"]
    assert "forced for the test" in rec["demoted"][1]["violations"][0]


def test_a_genuine_crash_still_fails_the_step(tmp_path, monkeypatch) -> None:
    # the fail-open path catches ONLY DerivedGateBlocked: a real crash (store IO error,
    # KeyError, ...) must still propagate, so a broken refresh never ships green with a
    # stale/missing briefing. This locks the narrow-except the exit-0 path depends on.
    def crash(out_dir):
        raise ValueError("genuine crash, not a gate trip")

    monkeypatch.setattr(reason, "write", crash)
    with pytest.raises(ValueError):
        reason.main([str(tmp_path)])


def _stub_briefing(out_dir: Path) -> Path:
    p = out_dir / "ai_briefing.json"
    p.write_text(json.dumps({"tier": "DERIVED", "claims": []}))
    return p


def test_a_recovered_briefing_clears_its_stale_demotion(tmp_path, monkeypatch) -> None:
    # last refresh's gate trip left an ai_briefing demotion record; this run's briefing
    # passes, so the record must be cleared — else the Source Ledger shows the layer
    # "demoted to dark" while a fresh briefing renders right beside it.
    (tmp_path / "demotions.json").write_text(
        json.dumps({"note": "n", "demoted": [
            {"stem": "news", "violations": ["x"]},
            {"stem": "ai_briefing", "violations": ["last week"]},
        ]})
    )
    monkeypatch.setattr(reason, "write", lambda out_dir: _stub_briefing(Path(out_dir)))
    assert reason.main([str(tmp_path)]) == 0
    rec = json.loads((tmp_path / "demotions.json").read_text())
    assert [d["stem"] for d in rec["demoted"]] == ["news"], "ai_briefing cleared; news kept"

    # when ai_briefing was the ONLY thing dark, the whole receipt file is removed
    (tmp_path / "demotions.json").write_text(
        json.dumps({"note": "n", "demoted": [{"stem": "ai_briefing", "violations": ["x"]}]})
    )
    assert reason.main([str(tmp_path)]) == 0
    assert not (tmp_path / "demotions.json").exists()
