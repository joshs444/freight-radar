"""Freight Radar detection brain (Wave 2 core + Wave 5 depth).

Wave 2: STL(period=7, robust) residual + trailing rolling z-score over each
entity's daily series. Chokepoint transit collapses/spikes and port activity
drops/congestion spikes become ``fct_flags`` rows with real, Python-computed
numbers.

Wave 5 hardening:
  * change-point gate (CUSUM + ruptures PELT) — confirm a z-trip only when it sits
    on a real level shift, cutting single-day false positives (``changepoint``);
  * Cape-of-Good-Hope reroute divergence detector (``cape_reroute``);
  * flag lifecycle new/ongoing/escalated/resolved with hysteresis (``lifecycle``);
  * holiday demand-dip suppression for benign seasonal lulls (``holidays``).
"""

from __future__ import annotations

from .cape_reroute import detect_cape_reroute
from .changepoint import changepoint_confirms, cusum_trips, pelt_breakpoints
from .detectors import (
    DetectionConfig,
    Flag,
    detect_series,
    load_config,
    severity_score,
)
from .holidays import apply_holiday_suppression, in_holiday_window
from .lifecycle import apply_lifecycle

__all__ = [
    "DetectionConfig",
    "Flag",
    "detect_series",
    "load_config",
    "severity_score",
    # Wave 5
    "changepoint_confirms",
    "cusum_trips",
    "pelt_breakpoints",
    "detect_cape_reroute",
    "apply_lifecycle",
    "apply_holiday_suppression",
    "in_holiday_window",
]
