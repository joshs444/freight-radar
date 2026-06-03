"""Wave 5: change-point gate — CUSUM + ruptures PELT over the STL residual.

The Wave-2 detector flags on the rolling z of the STL residual alone. A single
noisy day can spike |z| past the threshold without any genuine level shift, which
floods the "current issues" rail with false positives. This module adds a
confirmation gate:

    a flagged day survives only when
        (|z| trips  OR  CUSUM trips)            -- something moved
        AND a PELT breakpoint lies within        -- the move is a real level shift
            ``pelt_window`` days of that day

CUSUM (two-sided, Page's test) accumulates standardised residual drift; it catches
a *sustained* shift that a one-day z might miss or over-call. PELT
(``ruptures.Pelt(model="rbf")``) returns the residual's change-point set; requiring
a breakpoint near the flagged day rejects an isolated spike whose neighbourhood has
no structural break. The gate is config-driven (``use_changepoint_gate``) and
purely *subtractive* — it can only suppress, never invent, a flag.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import ruptures as rpt

from .detectors import DetectionConfig


def cusum_trips(resid: pd.Series, cfg: DetectionConfig, end: int) -> bool:
    """Two-sided standardised CUSUM up to ``end`` crosses +/- ``cusum_h``.

    The residual is standardised by the trailing ``z_window`` stats (the same
    baseline the z-score uses), then Page's recursion accumulates drift beyond a
    slack ``cusum_k``; |S+| or |S-| reaching ``cusum_h`` means a sustained shift.
    Returns False on a degenerate (constant) window.
    """
    win = min(cfg.z_window, end)
    if win < 2:
        return False
    base = resid.iloc[end - win : end]
    mu = float(base.mean())
    sd = float(base.std(ddof=1))
    if not np.isfinite(sd) or sd == 0.0:
        return False
    s_hi = s_lo = 0.0
    # accumulate over the trailing window up to and including the flagged day
    for i in range(end - win, end + 1):
        x = (float(resid.iloc[i]) - mu) / sd
        s_hi = max(0.0, s_hi + x - cfg.cusum_k)
        s_lo = min(0.0, s_lo + x + cfg.cusum_k)
        if s_hi >= cfg.cusum_h or s_lo <= -cfg.cusum_h:
            return True
    return False


def pelt_breakpoints(resid: pd.Series, cfg: DetectionConfig) -> list[int]:
    """Positional change-points of the residual via ruptures Pelt(model='rbf').

    Returns the 0-based indices at which a new segment *begins* (ruptures' final
    entry, len(series), is dropped). Empty when the series is too short.
    """
    x = resid.to_numpy(dtype=float).reshape(-1, 1)
    if len(x) < cfg.pelt_min_size * 2:
        return []
    algo = rpt.Pelt(model="rbf", min_size=cfg.pelt_min_size).fit(x)
    bkps = algo.predict(pen=cfg.pelt_penalty)
    return [b for b in bkps if b < len(x)]


def changepoint_confirms(resid: pd.Series, cfg: DetectionConfig, end: int) -> bool:
    """True iff a PELT breakpoint lies within ``pelt_window`` days of ``end``.

    This is the AND-side of the gate; the OR-side (|z| or CUSUM) is evaluated by
    the caller. A breakpoint *near* the flagged day means the anomaly sits on a
    genuine structural level shift rather than on isolated noise.
    """
    bkps = pelt_breakpoints(resid, cfg)
    return any(abs(b - end) <= cfg.pelt_window for b in bkps)
