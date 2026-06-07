"""P6 capstone — the DERIVED briefing is grounded, association-only, and admissible.

The reasoner is offline (Claude Code), but its output is gated in CI like everything else:
every claim cites a real layer, carries no causal/forecast verb, and owns no number. (The
quarantine — derived/ can't reach the fact path, and nothing imports derived/ — is proven in
test_layer_firewall.)
"""

from __future__ import annotations

from pathlib import Path

from freight_radar.derived.briefing import load, validate
from freight_radar.registry.layers import REGISTRY, Kind, by_id

BRIEFING = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data" / "ai_briefing.json"
VALID_IDS = {d.id for d in REGISTRY}


def test_ai_briefing_is_a_registered_derived_layer() -> None:
    d = by_id("ai_briefing")
    assert d.kind is Kind.DERIVED
    assert d.metric is None  # DERIVED owns no number, by construction


def test_committed_briefing_passes_the_honesty_gates() -> None:
    violations = validate(load(BRIEFING), VALID_IDS)
    assert violations == [], violations


def test_every_claim_cites_a_real_layer() -> None:
    briefing = load(BRIEFING)
    assert briefing["tier"] == "DERIVED" and briefing["claims"]
    for c in briefing["claims"]:
        assert c["cites"], "every claim must trace to the store"
        assert all(cite in VALID_IDS for cite in c["cites"]), c


def test_validate_rejects_ungrounded_causal_or_metric_claims() -> None:
    base = {"tier": "DERIVED", "agent_model": "claude", "claims": []}
    valid = {"stress"}
    assert validate({**base, "claims": [{"text": "x", "cites": []}]}, valid)  # zero cites
    assert validate({**base, "claims": [{"text": "x", "cites": ["nope"]}]}, valid)  # bad cite
    assert validate(  # causal verb
        {**base, "claims": [{"text": "the drop was caused by the quake", "cites": ["stress"]}]},
        valid,
    )
    assert validate({**base, "metric": 5, "claims": [{"text": "x", "cites": ["stress"]}]}, valid)
    assert validate({"tier": "SPINE", "agent_model": "c", "claims": [{"text": "x", "cites": ["stress"]}]}, valid)
    # a clean briefing passes
    assert (
        validate(
            {**base, "claims": [{"text": "stress reads 41.6", "cites": ["stress"]}]},
            valid,
        )
        == []
    )
