"""The honest-reasoning contract keystone — a claim cannot be ungrounded BY TYPE, an
association is a typed object, and ground_or_abstain is the one shared grounding law."""

from __future__ import annotations

from pathlib import Path

import pytest

from freight_radar.derived.contract import (
    ABSTAIN,
    AssociationObj,
    Claim,
    RetrievedObservation,
    ground_or_abstain,
)

DATA = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"


def test_a_claim_with_zero_cites_is_unconstructable() -> None:
    # the honesty thesis as a type: you cannot represent an ungrounded sentence in memory
    with pytest.raises(ValueError):
        Claim(text="freight is bad", cites=())
    # a cited claim constructs and normalizes cites to a tuple
    c = Claim(text="stress reads 41.6", cites=["stress"])
    assert c.cites == ("stress",)


def test_association_is_a_typed_object_not_prose() -> None:
    a = AssociationObj(
        layer_a="commodities",
        layer_b="freight_rate",
        method="lead_lag",
        window="12mo",
        confounder_note="both move with global demand — not evidence one drives the other",
        lag=2,
    )
    assert a.method == "lead_lag"
    # a fabricated stat method is rejected
    with pytest.raises(ValueError):
        AssociationObj("a", "b", method="causes", window="12mo", confounder_note="x")
    # an association that can't name a confounder is inadmissible
    with pytest.raises(ValueError):
        AssociationObj("a", "b", method="pearson", window="12mo", confounder_note="  ")


def test_retrieved_observation_is_frozen_and_lineage_stamped() -> None:
    o = RetrievedObservation(
        entity_key="pw:port694",
        metric_key="portcalls_total",
        value=12.0,
        method="observed port calls (IMF PortWatch)",
        as_of="2026-05-31",
        knowledge_time="2026-06-07T00:00:00",
        tier="SPINE",
        lineage_run_id="run-123",
    )
    assert o.tier == "SPINE" and o.lineage_run_id == "run-123"
    with pytest.raises(Exception):
        o.value = 99  # frozen — the model can't mutate a retrieved observation


def test_ground_or_abstain_returns_a_claim_when_every_cite_grounds() -> None:
    c = ground_or_abstain("stress is elevated", ["stress"], out_dir=DATA)
    assert isinstance(c, Claim) and c.cites == ("stress",)


def test_ground_or_abstain_drops_the_claim_on_any_ungrounded_cite() -> None:
    # a claim citing something the store doesn't measure is dropped — the honest 'no'
    assert ground_or_abstain("tensions rising", ["geopolitical_tension"], out_dir=DATA) is ABSTAIN
    # mixed: one good cite + one bad → the WHOLE claim drops (any abstain kills it)
    assert ground_or_abstain("x", ["stress", "not_a_layer"], out_dir=DATA) is ABSTAIN
    # no cites at all → abstain (never a fabricated claim)
    assert ground_or_abstain("x", [], out_dir=DATA) is ABSTAIN


def test_abstain_is_falsy() -> None:
    assert not ABSTAIN
    assert bool(ground_or_abstain("x", ["nope"], out_dir=DATA)) is False
