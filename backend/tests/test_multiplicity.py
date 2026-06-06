"""P2 keystone — the FDR multiplicity gate holds: pure noise stays under budget, and
genuine anomalies survive. This is the §8 white-noise predicate that lets the spine go
from 28 series to ~2065 without manufacturing flags.
"""

from __future__ import annotations

import random

from freight_radar.detect.multiplicity import benjamini_hochberg, control_z, two_sided_p


def test_pure_white_noise_manufactures_almost_no_flags() -> None:
    # 2065 pure-noise z-scores (what a naive |z|>=3 cut would turn into ~5-6 fake flags).
    rng = random.Random(42)
    z = [rng.gauss(0.0, 1.0) for _ in range(2065)]
    keep, res = control_z(z, q=0.10)
    # under the global null, BH is conservative — it should let ~0 through, never a pile.
    assert res.n_significant <= 3, f"FDR let {res.n_significant} white-noise flags through"
    assert sum(keep) == res.n_significant


def test_genuine_strong_anomalies_survive() -> None:
    rng = random.Random(1)
    z = [rng.gauss(0.0, 1.0) for _ in range(2000)] + [7.5, 8.0, 9.0, 10.0]
    keep, res = control_z(z, q=0.10)
    assert sum(keep[-4:]) == 4, "FDR wrongly rejected genuine z=7.5-10 anomalies"
    assert res.expected_false <= res.q * res.n_significant + 1e-9


def test_realized_false_rate_under_budget_across_trials() -> None:
    # repeat the white-noise experiment; the realized false-discovery count must stay tiny.
    total_false = 0
    trials = 20
    for seed in range(trials):
        rng = random.Random(seed)
        z = [rng.gauss(0.0, 1.0) for _ in range(1000)]
        keep, _ = control_z(z, q=0.10)
        total_false += sum(keep)  # every one is false (pure noise)
    # ~0 expected; allow a tiny slack. A blanket |z|>=3 would yield ~1.3 per trial = ~27 here.
    assert total_false <= 5, f"realized false flags {total_false} over {trials} noise trials"


def test_bh_edges() -> None:
    assert benjamini_hochberg([], 0.1) == []
    assert all(benjamini_hochberg([1e-12] * 10, 0.1))  # all genuinely significant
    assert not any(benjamini_hochberg([0.9] * 10, 0.1))  # all null
    assert two_sided_p(0.0) == 1.0  # z=0 is maximally unremarkable
    assert two_sided_p(100.0) < 1e-9  # z=100 is essentially impossible under noise
