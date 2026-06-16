"""Wave 5: Cape-of-Good-Hope reroute divergence detector — the signature story.

When Red Sea transit is unsafe, carriers divert south around the Cape of Good Hope:
Suez Canal + Bab el-Mandeb Strait traffic falls while Cape traffic rises. A single
chokepoint anomaly can't tell that story; the *divergence* is the signal.

In a trailing ``cape_window`` (default 14d) window we compare each waterway's mean
to its immediately-preceding window:

    red_sea_pct = pct change of (Suez + Bab combined) latest-window vs prior-window
    cape_pct    = pct change of Cape latest-window vs prior-window

A ``cape_reroute`` flag fires iff the Red Sea side is DOWN and the Cape side is UP,
each by at least ``cape_min_divergence`` percent. Exactly one flag is emitted,
placed at the Cape's lat/lon, entity "Red Sea → Cape of Good Hope reroute", with
both real magnitudes stated in the brief. Because that entity is a story string —
not a chokepoint name — the published flag also carries structured ``chokepoints``
refs (``CAPE_CHOKEPOINTS``) so exposure can match lanes routed through the legs the
diversion avoids. If the data shows no such divergence the detector simply returns
None — it never fabricates the signal.

Severity scales with how far past the trigger both legs moved (the combined
absolute divergence, saturating at ~60pp), weighted up because a reroute is a
high-economic-impact event.
"""

from __future__ import annotations

import pandas as pd

from .detectors import (
    METHOD,
    SOURCE,
    DetectionConfig,
    Flag,
    make_flag_id,
)

CAPE_KIND = "cape_reroute"
CAPE_ENTITY = "Red Sea → Cape of Good Hope reroute"
# The real chokepoints this reroute disrupts, by the canonical names the routing
# model uses (business/exposure.py CORRIDOR / REROUTE_DELAY). CAPE_ENTITY above is
# deliberately descriptive and matches no lane's route — exposure consumes these
# structured refs instead, so the signature flag never reads as $0 exposure (H1-B).
CAPE_CHOKEPOINTS = ("Suez Canal", "Bab el-Mandeb Strait")


def _window_pct(values: pd.Series, window: int) -> tuple[float, float, float]:
    """Mean of the trailing ``window``, the window before it, and the pct change.

    Returns (latest_mean, prior_mean, pct). Needs >= 2*window points; the caller
    guards on that. pct is 0.0 when the prior mean is 0.
    """
    latest = float(values.iloc[-window:].mean())
    prior = float(values.iloc[-2 * window : -window].mean())
    pct = ((latest - prior) / prior * 100.0) if prior else 0.0
    return latest, prior, pct


def detect_cape_reroute(
    *,
    red_sea: pd.Series,
    cape: pd.Series,
    cape_lat: float | None,
    cape_lon: float | None,
    as_of,
    cfg: DetectionConfig,
) -> Flag | None:
    """Emit ONE ``cape_reroute`` Flag on a real Red-Sea-down / Cape-up divergence.

    ``red_sea`` is the combined (summed) daily Suez+Bab series; ``cape`` the Cape
    daily series — both date-indexed and sorted. ``as_of`` is a ``date``. Returns
    None when either series is too short or the divergence test isn't met.
    """
    red_sea = red_sea.sort_index()
    cape = cape.sort_index()
    w = cfg.cape_window
    if len(red_sea) < 2 * w or len(cape) < 2 * w:
        return None

    rs_latest, rs_prior, rs_pct = _window_pct(red_sea, w)
    cp_latest, cp_prior, cp_pct = _window_pct(cape, w)

    thr = cfg.cape_min_divergence
    if not (rs_pct <= -thr and cp_pct >= thr):
        return None  # no sustained down/up divergence -> do not fire

    # severity: combined absolute divergence, saturating at ~60 percentage points,
    # weighted high (0.95) because a Red-Sea reroute is a major-impact event.
    divergence = abs(rs_pct) + abs(cp_pct)
    severity = int(round(100 * min(divergence / 60.0, 1.0) * 0.95))

    as_of_str = as_of.isoformat()
    headline = (
        f"Red Sea → Cape reroute: Suez+Bab transit down {abs(rs_pct):.0f}%, "
        f"Cape of Good Hope up {cp_pct:.0f}%"
    )
    brief = (
        f"Over the trailing **{w} days**, combined **Suez Canal + Bab el-Mandeb** "
        f"transit fell **{abs(rs_pct):.0f}%** (to ~{rs_latest:.0f}/day from "
        f"~{rs_prior:.0f}/day) while **Cape of Good Hope** rose **{cp_pct:.0f}%** "
        f"(to ~{cp_latest:.0f}/day from ~{cp_prior:.0f}/day) — the classic "
        f"Red Sea avoidance / Cape diversion signature.\n\n"
        f"_Method: {METHOD}; window-over-window divergence. Source: {SOURCE}._"
    )
    return Flag(
        flag_id=make_flag_id(CAPE_KIND, cfg.cape_portid, as_of),
        kind=CAPE_KIND,
        entity=CAPE_ENTITY,
        portid=cfg.cape_portid,
        lat=cape_lat,
        lon=cape_lon,
        severity=severity,
        headline=headline,
        brief_md=brief,
        metric="n_total",
        value=round(rs_latest, 2),
        baseline=round(rs_prior, 2),
        pct_change=round(rs_pct, 1),
        zscore=round(cp_pct, 2),  # surface the Cape's up-move alongside the RS down
        as_of=as_of_str,
    )
