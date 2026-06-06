"""Multiplicity control — Benjamini-Hochberg FDR over a family of flag candidates.

Testing ~2065 ports for an anomaly at |z| ≥ 3 will, on *pure noise*, manufacture
~2065 · 2Φ(−3) ≈ 5–6 "flags" that mean nothing. Going wide without correction quietly
breaks the honesty claim ("these are real disruptions"). FDR caps the *expected fraction*
of false flags among those raised at a declared budget q, over a frozen domain family —
so the brand survives the 28 → 2065 extension. See STANDPOINT-VISION.md §7.3 + §8 (the
realized false-flag rate under injected white noise must stay ≤ the declared budget).

This is pure + deterministic (no DB, no network), so the white-noise guarantee is a CI
predicate, not a hope. It is intentionally standalone here; the per-series detection wires
it in when the spine widens past the 28 chokepoints.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


def two_sided_p(z: float) -> float:
    """P(|Z| ≥ |z|) for a standard normal — the chance pure noise reaches this extreme."""
    return math.erfc(abs(z) / math.sqrt(2.0))


@dataclass(frozen=True)
class FDRResult:
    q: float  # the declared false-discovery budget
    n_tested: int
    n_significant: int  # how many candidates survive FDR
    threshold_p: float  # the BH p-value cutoff (0.0 if nothing survives)
    expected_false: float  # q · n_significant — the honest "expect ≤k of these are noise"


def benjamini_hochberg(pvalues: list[float], q: float = 0.10) -> list[bool]:
    """Return a keep-mask (True = survives FDR) for each p-value, controlling FDR at q.

    Standard step-up BH: sort ascending, find the largest rank k with p(k) ≤ (k/m)·q, and
    reject every candidate at rank ≤ k (i.e. with the k smallest p-values).
    """
    m = len(pvalues)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: pvalues[i])
    kmax = 0
    for rank, idx in enumerate(order, start=1):
        if pvalues[idx] <= (rank / m) * q:
            kmax = rank
    keep = [False] * m
    for rank, idx in enumerate(order, start=1):
        if rank <= kmax:
            keep[idx] = True
    return keep


def control_z(zscores: list[float], q: float = 0.10) -> tuple[list[bool], FDRResult]:
    """Apply BH-FDR to a family of z-scores. Returns (keep-mask, summary)."""
    pvals = [two_sided_p(z) for z in zscores]
    keep = benjamini_hochberg(pvals, q)
    n_sig = sum(keep)
    threshold_p = max((pvals[i] for i in range(len(pvals)) if keep[i]), default=0.0)
    return keep, FDRResult(
        q=q,
        n_tested=len(zscores),
        n_significant=n_sig,
        threshold_p=threshold_p,
        expected_false=round(q * n_sig, 3),
    )
