"""The DERIVED reasoner's fail-closed gate + the reasoner itself.

The committed briefing must pass the full gate (validate + attribution + abstention +
provenance); the gate must FIRE on an unentailed number, a causal claim, and a bad cite; and
the reasoner must produce a gate-clean briefing from the live store. This is the eval that
lets an LLM-authored briefing ship at all — a hallucinated number fails here, in CI.
"""

from __future__ import annotations

import json
from pathlib import Path

from freight_radar.derived import reason
from freight_radar.derived.gate import attribution_violations, gate_briefing
from freight_radar.registry.layers import REGISTRY

DATA = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"
VALID = {d.id for d in REGISTRY}
BRIEFING = DATA / "ai_briefing.json"


def test_committed_briefing_passes_the_whole_gate() -> None:
    b = json.loads(BRIEFING.read_text())
    assert gate_briefing(b, VALID, out_dir=DATA) == {}, gate_briefing(b, VALID, out_dir=DATA)


def test_attribution_fires_on_an_unentailed_number() -> None:
    # a fabricated value the cited layer does not contain must be caught (the hallucination gate)
    bad = {
        "tier": "DERIVED",
        "agent_model": "x",
        "claims": [{"text": "The stress index reads 99.9.", "cites": ["stress"]}],
    }
    assert attribution_violations(bad, out_dir=DATA), "99.9 is not in stress.json — must fail"
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
    import pytest

    with pytest.raises(reason.DerivedGateBlocked):
        reason.write(DATA)
