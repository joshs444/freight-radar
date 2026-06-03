"""Freight Radar detection brain (Wave 2).

STL(period=7, robust) residual + trailing rolling z-score over each entity's daily
series. Chokepoint transit collapses/spikes and port activity drops/congestion
spikes become ``fct_flags`` rows with real, Python-computed numbers.
"""

from __future__ import annotations

from .detectors import (
    DetectionConfig,
    Flag,
    detect_series,
    load_config,
    severity_score,
)

__all__ = [
    "DetectionConfig",
    "Flag",
    "detect_series",
    "load_config",
    "severity_score",
]
