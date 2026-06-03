"""Detection brain: STL residual + rolling z-score over each entity's daily series.

Pipeline per series (a single entity's metric over time, indexed by date):

1. STL(period=stl_period, robust=True) decomposition -> keep the **residual**
   (de-trended, de-seasonalised). Weekly seasonality (weekend dips) and slow drift
   are removed so only genuine shocks survive.
2. Rolling z-score of that residual over a trailing ``z_window``:
       z = (latest_resid - rolling_mean(resid)) / rolling_std(resid)
   computed on the window ending just before the latest point (so the latest day is
   scored against its own recent history, not itself).
3. A plain pct_change of the *raw* value vs its trailing-28d mean, for the headline.

A flag fires when z <= collapse_z (collapse / drop) or z >= spike_z (spike).

Severity (0..100), explicit and visible:

    severity = round(100 * magnitude * persistence * econ_weight)

      magnitude   = min(|z| / 5, 1)                  -- 5-sigma saturates the bar
      persistence = max(0.4, frac of trailing 7 days with |z| >= persistence_z)
                    -- a sharp 1-day shock still scores (floor 0.4); a sustained
                       multi-day anomaly scores higher
      econ_weight = 0.6 + 0.4 * vessel_pct          -- 0.6..1.0 from the entity's
                    vessel_count_total percentile (a busier waterway weighs more)

Every number in a Flag (value, baseline, pct_change, zscore) is computed here from
the data — nothing is invented. Briefs are template-first with these floats
string-substituted in.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from statsmodels.tsa.seasonal import STL

from ..config import BACKEND_DIR

CONFIG_PATH = BACKEND_DIR / "config" / "detection.yaml"

SOURCE = "IMF PortWatch — daily granularity, refreshed weekly"
METHOD = "STL(7,robust) residual + 28d rolling z"

# kind labels keyed by (entity_type, direction).
KINDS = {
    ("chokepoint", "down"): "chokepoint_transit_collapse",
    ("chokepoint", "up"): "chokepoint_transit_spike",
    ("port", "down"): "port_activity_drop",
    ("port", "up"): "port_congestion_spike",
}


@dataclass(frozen=True)
class DetectionConfig:
    stl_period: int = 7
    z_window: int = 28
    detection_window: int = 14
    collapse_z: float = -3.0
    spike_z: float = 3.5
    persistence_window: int = 7
    persistence_z: float = 2.0
    top_n_ports: int = 75
    min_history_days: int = 35


@dataclass(frozen=True)
class Flag:
    """One detected anomaly. Numbers are all Python-computed (see module docstring)."""

    flag_id: str
    kind: str
    entity: str
    portid: str
    lat: float | None
    lon: float | None
    severity: int
    headline: str
    brief_md: str
    metric: str
    value: float
    baseline: float
    pct_change: float
    zscore: float
    as_of: str  # 'YYYY-MM-DD'
    source: str = SOURCE
    method: str = METHOD
    lifecycle: str = "new"


def load_config(path: str | Path = CONFIG_PATH) -> DetectionConfig:
    """Load thresholds from detection.yaml (pyyaml). Unknown keys are ignored."""
    raw = yaml.safe_load(Path(path).read_text()) or {}
    fields = DetectionConfig.__dataclass_fields__
    return DetectionConfig(**{k: raw[k] for k in fields if k in raw})


# --- numeric core ----------------------------------------------------------


def stl_residual(values: pd.Series, period: int) -> pd.Series:
    """STL(period, robust) residual of a value series. Index is preserved.

    The trend smoother is pinned to ~half the series length (odd, >= 2*period+1).
    Left at STL's default, the LOESS trend chases a multi-day step at the series
    *end* and re-levels onto it within a few days — which would hide exactly the
    sustained collapse/spike we want to catch (the shock leaks into the trend
    instead of the residual). A long trend window keeps only the slow secular
    drift in the trend, so genuine shocks stay in the residual to be z-scored.
    """
    n = len(values)
    trend = max(period * 2 + 1, (int(n * 0.5)) | 1)  # force odd
    return STL(values.astype(float), period=period, robust=True, trend=trend).fit().resid


def rolling_zscore(resid: pd.Series, window: int, end: int | None = None) -> float:
    """Z of the residual at position ``end`` vs the ``window`` residuals before it.

    The scored point is held out of its own baseline (the window ends one step
    earlier), so a shock can't inflate the mean/std it's measured against. ``end``
    defaults to the last point. Returns 0.0 when the trailing window is degenerate
    (constant), which never trips a threshold.
    """
    if end is None:
        end = len(resid) - 1
    win = min(window, end)
    if win < 2:
        return 0.0
    latest = float(resid.iloc[end])
    trailing = resid.iloc[end - win : end]
    mu = float(trailing.mean())
    sd = float(trailing.std(ddof=1))
    if not np.isfinite(sd) or sd == 0.0:
        return 0.0
    return (latest - mu) / sd


def pct_vs_baseline(
    values: pd.Series, window: int, end: int | None = None
) -> tuple[float, float, float]:
    """Raw value at ``end``, its trailing-``window`` mean (baseline), and pct change."""
    if end is None:
        end = len(values) - 1
    win = min(window, end)
    latest = float(values.iloc[end])
    trailing = values.iloc[end - win : end]
    baseline = float(trailing.mean())
    pct = ((latest - baseline) / baseline * 100.0) if baseline else 0.0
    return latest, baseline, pct


def _persistence(resid: pd.Series, cfg: DetectionConfig, end: int) -> float:
    """Fraction of the ``persistence_window`` days up to ``end`` with |z| >= threshold.

    Floored at 0.4 so a sharp single-day shock still scores; a sustained multi-day
    anomaly climbs toward 1.0.
    """
    anomalous = 0
    for i in range(end - cfg.persistence_window + 1, end + 1):
        if i < 1:
            continue
        if abs(rolling_zscore(resid, cfg.z_window, end=i)) >= cfg.persistence_z:
            anomalous += 1
    return max(0.4, anomalous / cfg.persistence_window)


def severity_score(
    zscore: float,
    resid: pd.Series,
    cfg: DetectionConfig,
    econ_weight: float,
    end: int | None = None,
) -> int:
    """0..100 severity. See module docstring for the formula and rationale."""
    if end is None:
        end = len(resid) - 1
    magnitude = min(abs(zscore) / 5.0, 1.0)
    persistence = _persistence(resid, cfg, end)
    return int(round(100 * magnitude * float(np.clip(persistence, 0, 1)) * econ_weight))


# --- flag assembly ---------------------------------------------------------


def make_flag_id(kind: str, portid: str, as_of: date) -> str:
    """sha1(kind|portid|isoYear-Wweek)[:16] — dedup-stable per ISO week."""
    iso_year, iso_week, _ = as_of.isocalendar()
    key = f"{kind}|{portid}|{iso_year}-W{iso_week:02d}"
    return hashlib.sha1(key.encode()).hexdigest()[:16]


def _brief(
    *,
    entity: str,
    entity_type: str,
    direction: str,
    value: float,
    baseline: float,
    pct: float,
    zscore: float,
    as_of: str,
    unit: str,
) -> tuple[str, str]:
    """Template-first headline + markdown brief; every number is substituted in."""
    verb = "fell to" if direction == "down" else "surged to"
    rel = "below" if direction == "down" else "above"
    headline = (
        f"{entity} {('transit' if entity_type == 'chokepoint' else 'activity')} "
        f"{abs(pct):.0f}% {rel} its 28-day norm"
    )
    brief = (
        f"**{entity}** {('transit' if entity_type == 'chokepoint' else 'port calls')} "
        f"{verb} **{value:.0f} {unit}** on {as_of}, "
        f"**{abs(pct):.0f}% {rel}** its 28-day norm of ~{baseline:.0f}/day "
        f"(z = {zscore:+.1f})."
    )
    if entity_type == "port":
        brief += (
            "\n\n_\"Congestion\" here is inferred from a surge/drop in daily port "
            "calls, not from direct vessel dwell-time data._"
        )
    brief += (
        f"\n\n_Method: {METHOD}. Source: {SOURCE}._"
    )
    return headline, brief


def detect_series(
    *,
    portid: str,
    entity: str,
    entity_type: str,
    metric: str,
    values: pd.Series,
    as_of: date,
    cfg: DetectionConfig,
    lat: float | None = None,
    lon: float | None = None,
    econ_weight: float = 1.0,
    unit: str = "vessels",
) -> Flag | None:
    """Run the full pipeline on one entity's daily series; return a Flag or None.

    ``values`` is a date-indexed numeric Series (one entity, one metric). The
    trailing ``detection_window`` days are scanned and the entity is flagged on the
    day its rolling-z is most extreme *and* crosses a threshold — a "current issues"
    rail should surface the day a shock actually peaked, not whichever calendar day
    happens to be last (which is often calm). Every number binds to that peak day.
    Returns None when history is too short or nothing in the window crosses.
    """
    values = values.sort_index()
    if len(values) < cfg.min_history_days:
        return None

    resid = stl_residual(values, cfg.stl_period)

    # Scan the trailing detection window; keep the threshold-crossing day with the
    # largest |z|. ``as_of`` (passed in) is the data's max date for provenance, but
    # the flag's own as_of binds to the peak day.
    n = len(values)
    best_end: int | None = None
    best_z = 0.0
    for end in range(max(cfg.z_window, n - cfg.detection_window), n):
        z = rolling_zscore(resid, cfg.z_window, end=end)
        if (z <= cfg.collapse_z or z >= cfg.spike_z) and abs(z) > abs(best_z):
            best_z, best_end = z, end
    if best_end is None:
        return None

    z = best_z
    direction = "down" if z <= cfg.collapse_z else "up"
    value, baseline, pct = pct_vs_baseline(values, cfg.z_window, end=best_end)
    kind = KINDS[(entity_type, direction)]
    severity = severity_score(z, resid, cfg, econ_weight, end=best_end)
    peak_date = values.index[best_end].date()
    as_of_str = peak_date.isoformat()
    headline, brief = _brief(
        entity=entity,
        entity_type=entity_type,
        direction=direction,
        value=value,
        baseline=baseline,
        pct=pct,
        zscore=z,
        as_of=as_of_str,
        unit=unit,
    )
    return Flag(
        flag_id=make_flag_id(kind, portid, peak_date),
        kind=kind,
        entity=entity,
        portid=portid,
        lat=lat,
        lon=lon,
        severity=severity,
        headline=headline,
        brief_md=brief,
        metric=metric,
        value=round(value, 2),
        baseline=round(baseline, 2),
        pct_change=round(pct, 1),
        zscore=round(z, 2),
        as_of=as_of_str,
    )
