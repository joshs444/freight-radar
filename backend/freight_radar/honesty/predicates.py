"""Registry-level honesty predicates — the executable tier/source/cost spec.

Pure functions returning a list of violation strings (empty == clean). The CI honesty
suite asserts each is empty; the scorecard reports the same checks as a trend — so
"are we honest?" is computed exactly one way, from the registry, never re-stated.
"""

from __future__ import annotations

from ..registry.layers import REGISTRY, Kind, Producer
from .lexicon import scan as scan_causal

# The zero-marginal-cost gate: a source must be free, with at most a free key.
_FREE_AUTH = {"none", "free_key", "oauth_free"}

# Layers that ingest an EXTERNAL observation (vs derive from the already-sourced spine)
# must declare provenance: the cited/signal ring + the off-loop producers.
_EXTERNAL_PRODUCERS = {Producer.AIS, Producer.EXTERNAL, Producer.CLIENT}


def _needs_source(d) -> bool:
    return d.kind in (Kind.CONTEXT, Kind.SIGNAL) or d.producer in _EXTERNAL_PRODUCERS


def tier_violations() -> list[str]:
    out: list[str] = []
    for d in REGISTRY:
        if d.kind not in (Kind.SPINE, Kind.SIGNAL, Kind.CONTEXT, Kind.DERIVED):
            out.append(f"{d.id}: invalid kind {d.kind!r}")
        if d.kind is Kind.CONTEXT and d.metric is not None:
            out.append(f"{d.id}: CONTEXT must not own a metric (passthrough), got {d.metric!r}")
        if d.kind is Kind.DERIVED and d.metric is not None:
            out.append(f"{d.id}: DERIVED must own no metric (commentary, not a number)")
        if d.kind is Kind.SIGNAL and not d.metric:
            out.append(f"{d.id}: SIGNAL must declare the scalar it owns (metric=None)")
    return out


def cost_violations() -> list[str]:
    out: list[str] = []
    for d in REGISTRY:
        s = d.source
        if s is None:
            continue
        if s.cost != "free":
            out.append(f"{d.id}: source cost {s.cost!r} — only 'free' is allowed")
        if s.auth not in _FREE_AUTH:
            out.append(f"{d.id}: source auth {s.auth!r} not in {sorted(_FREE_AUTH)}")
    return out


def source_completeness_violations() -> list[str]:
    out: list[str] = []
    for d in REGISTRY:
        s = d.source
        if s is None:
            continue
        for field in ("name", "url", "license"):
            if not getattr(s, field):
                out.append(f"{d.id}: source.{field} is empty")
    return out


def source_coverage_violations() -> list[str]:
    """Every external-input layer (CONTEXT/SIGNAL/off-loop) must declare a Source."""
    return [d.id for d in REGISTRY if _needs_source(d) and d.source is None]


def causal_copy_violations() -> list[str]:
    out: list[str] = []
    for d in REGISTRY:
        for label, text in (("honesty_note", d.honesty_note), ("metric", d.metric)):
            if text and (hits := scan_causal(text)):
                out.append(f"{d.id}.{label}: causal/forecast verb {hits}")
    return out


def source_coverage() -> dict:
    needs = [d for d in REGISTRY if _needs_source(d)]
    have = [d for d in needs if d.source is not None]
    return {
        "needs": len(needs),
        "have": len(have),
        "missing": [d.id for d in needs if d.source is None],
        "pct": round(100 * len(have) / len(needs), 1) if needs else 100.0,
    }


def all_violations() -> dict[str, list[str]]:
    return {
        "tier": tier_violations(),
        "zero_cost": cost_violations(),
        "source_completeness": source_completeness_violations(),
        "source_coverage": source_coverage_violations(),
        "causal_copy": causal_copy_violations(),
    }
