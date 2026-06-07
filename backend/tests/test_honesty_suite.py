"""Layer-1 invariants (honesty, generalized) — the executable honesty spec over the
registry. Each predicate is binary and registry-driven, so a new layer is covered for
free and the brand can't drift back into prose. See ACCEPTANCE-HARNESS.md (Layer 1) and
STANDPOINT-VISION.md §7.
"""

from __future__ import annotations

from dataclasses import replace

from freight_radar.honesty import predicates as P
from freight_radar.registry.layers import Kind, by_id


def test_tier_predicates() -> None:
    # CONTEXT owns no metric (passthrough); SIGNAL declares the scalar it owns; valid kinds.
    assert P.tier_violations() == []


def test_spine_is_one() -> None:
    # the measured tier has exactly one root + a single-rooted acyclic provenance DAG.
    assert P.spine_root_violations() == [], P.spine_root_violations()


def test_spine_one_predicate_has_teeth(monkeypatch) -> None:
    """A malicious branch — a SECOND measured root, or a SPINE deriving from a CONTEXT layer
    — must fail the predicate. Proves the gate isn't vacuously green."""
    import freight_radar.honesty.predicates as PM
    from freight_radar.registry import layers as L

    real = list(L.REGISTRY)

    # case 1: a second measured root (a SPINE layer with derives_from=None)
    two_roots = tuple(replace(d, derives_from=None) if d.id == "flags" else d for d in real)
    monkeypatch.setattr(L, "REGISTRY", two_roots)
    monkeypatch.setattr(PM, "REGISTRY", two_roots)
    assert PM.spine_root_violations(), "two SPINE roots should fail"

    # case 2: a SPINE layer deriving from a non-SPINE (tier laundering)
    bad_edge = tuple(replace(d, derives_from="quakes") if d.id == "flags" else d for d in real)
    monkeypatch.setattr(L, "REGISTRY", bad_edge)
    monkeypatch.setattr(PM, "REGISTRY", bad_edge)
    assert PM.spine_root_violations(), "a SPINE deriving from CONTEXT should fail"


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
