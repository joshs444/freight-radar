"""Layer-4 (scorecard) — the honesty trend computes + is deterministic.

Minimal start: the metrics that already derive from the registry + predicates. The
scorecard is never a ship gate (correct != improving); this just proves it builds and
is stable run-to-run (modulo the timestamp).
"""

from __future__ import annotations

from freight_radar.honesty.scorecard import build_scorecard


def test_scorecard_structure_and_currently_all_green() -> None:
    s = build_scorecard()
    assert s["layers_total"] >= 20
    assert set(s["layers_by_tier"]) == {"SPINE", "SIGNAL", "CONTEXT", "DERIVED"}
    assert s["layers_by_tier"]["SIGNAL"] >= 1
    # P1 milestone: every honesty gate green.
    assert all(s["honesty_gates"].values()), s["honesty_gates"]
    assert s["honesty_ci_pass_rate"] == 100.0
    assert s["zero_cost_compliance_pct"] == 100.0
    assert s["source_coverage_pct"] == 100.0


def test_scorecard_is_deterministic_modulo_timestamp() -> None:
    a, b = build_scorecard(), build_scorecard()
    assert a == b  # build_scorecard() carries no timestamp; write() adds generated_at
