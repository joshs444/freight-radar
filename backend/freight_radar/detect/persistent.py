"""Persistent level-shift detector — the 'it happened a while ago but is still bad' case.

The STL+z detector in detectors.py scans only the trailing detection window for a
fresh change-point, so a disruption that shifted the level weeks/months ago and then
*persisted* is invisible: the 28-day rolling baseline has adapted to the new level, so
today-vs-baseline reads ~0. The flagship example is the Strait of Hormuz, which
collapsed ~95% in March 2026 (2026 Hormuz crisis) and has stayed there.

This detector compares the CURRENT level to the entity's own PRE-shift norm (a robust
high percentile of its rolling mean across the available window) and flags a sustained
departure. It is deterministic and complementary: it only fires for entities the fresh
detector did NOT already flag.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .detectors import SOURCE, DetectionConfig, Flag, make_flag_id

PERSIST_METHOD = "sustained level-shift vs pre-disruption norm"


def detect_persistent(
    *,
    portid: str,
    entity: str,
    values: pd.Series,
    cfg: DetectionConfig,
    lat: float | None = None,
    lon: float | None = None,
    econ_weight: float = 1.0,
    entity_type: str = "chokepoint",
    metric: str = "n_total",
    unit: str = "vessels",
) -> Flag | None:
    s = values.sort_index().astype(float)
    if len(s) < cfg.persist_min_history:
        return None

    roll = s.rolling(cfg.persist_roll, min_periods=max(5, cfg.persist_roll // 2)).mean().dropna()
    if roll.empty:
        return None
    reference = float(roll.quantile(0.80))          # the sustained pre-shift "normal"
    current = float(s.iloc[-cfg.persist_current:].mean())
    if reference < cfg.persist_min_level:           # too low-volume/noisy to judge
        return None

    pct = (current - reference) / reference * 100.0
    if abs(pct) < cfg.persist_min_pct:
        return None
    direction = "down" if pct < 0 else "up"

    # How many of the recent days sit clearly on the deviated side (>60% of the way
    # from the reference toward the current level)? Requires a sustained shift.
    thresh = reference * (0.6 if direction == "down" else 1.6)
    dev = (s < thresh) if direction == "down" else (s > thresh)
    days_persisted = int(dev.iloc[-cfg.persist_scan:].sum())
    if days_persisted < cfg.persist_days:
        return None

    # Date the shift to the steepest move in the 7-day rolling mean.
    roll7 = s.rolling(7, min_periods=3).mean()
    diff = roll7.diff()
    shift_idx = diff.idxmin() if direction == "down" else diff.idxmax()
    shift_date = shift_idx.date() if pd.notna(shift_idx) else s.index[-1].date()
    days_since = (s.index[-1].date() - shift_date).days

    magnitude = min(abs(pct) / 100.0, 1.0)
    persistence = min(days_persisted / max(cfg.persist_days * 2, 1), 1.0)
    severity = int(round(100 * magnitude * float(np.clip(persistence, 0, 1)) * econ_weight))

    kind = f"{entity_type}_persistent_{'collapse' if direction == 'down' else 'surge'}"
    rel = "below" if direction == "down" else "above"
    word = "transit" if entity_type == "chokepoint" else "activity"
    headline = f"{entity} {word} ~{abs(pct):.0f}% {rel} its pre-disruption norm (sustained)"
    brief = (
        f"**{entity}** has run at **~{current:.0f} {unit}/day** since around "
        f"**{shift_date.isoformat()}**, **~{abs(pct):.0f}% {rel}** its prior norm of "
        f"**~{reference:.0f}/day** — a level shift sustained for **~{days_since} days**.\n\n"
        f"_This is a persistent disruption, not a fresh blip. A 28-day rolling baseline "
        f"has since adapted to the new level, which is why a same-day anomaly detector "
        f"reads it as 'normal'; it is flagged by comparing today's level to the pre-shift "
        f"norm._\n\n_Method: {PERSIST_METHOD}. Source: {SOURCE}._"
    )
    return Flag(
        flag_id=make_flag_id(kind, portid, shift_date),
        kind=kind,
        entity=entity,
        portid=portid,
        lat=lat,
        lon=lon,
        severity=severity,
        headline=headline,
        brief_md=brief,
        metric=metric,
        value=round(current, 2),
        baseline=round(reference, 2),
        pct_change=round(pct, 1),
        zscore=0.0,
        as_of=shift_date.isoformat(),
        method=PERSIST_METHOD,
        lifecycle="ongoing",
    )
