"""Layer-1 invariants (honesty, generalized) — the executable honesty spec over the
registry. Each predicate is binary and registry-driven, so a new layer is covered for
free and the brand can't drift back into prose. See ACCEPTANCE-HARNESS.md (Layer 1) and
STANDPOINT-VISION.md §7.
"""

from __future__ import annotations

from freight_radar.honesty import predicates as P


def test_tier_predicates() -> None:
    # CONTEXT owns no metric (passthrough); SIGNAL declares the scalar it owns; valid kinds.
    assert P.tier_violations() == []


def test_zero_cost_gate() -> None:
    # every declared source is free, with at most a free key — no metered data, ever.
    assert P.cost_violations() == []


def test_source_completeness() -> None:
    # a declared source carries name + url + license (the source_manifest seed).
    assert P.source_completeness_violations() == []


def test_source_coverage() -> None:
    # every external-input layer (CONTEXT/SIGNAL/off-loop) declares provenance.
    assert P.source_coverage_violations() == [], (
        f"layers missing a Source: {P.source_coverage_violations()}"
    )


def test_no_causal_or_forecast_verbs_in_registry_copy() -> None:
    # the centrum failure mode, banned across every layer's honesty_note + metric copy.
    assert P.causal_copy_violations() == []
