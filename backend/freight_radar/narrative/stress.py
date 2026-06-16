"""Global Ocean Freight Stress Index (0-100) — the at-a-glance number.

One honest scalar that answers "how stressed is ocean freight right now?", plus a
historical curve so you can see the trend and momentum. Everything is computed in
Python from the same ``timeseries.json`` that already drives the scrubber/sparklines
— no new data, no new fetch, every value traceable.

Method (documented so it survives scrutiny):
  - Each of the 28 chokepoints gets an ECONOMIC WEIGHT = its *normal* vessel-CAPACITY
    (DWT) share — bigger ships carry far more trade, so Suez/Panama outweigh a busy
    short-sea strait like Dover instead of being averaged in by vessel count. "Normal"
    is the 80th percentile of the chokepoint's FULL PortWatch record (2019->now), NOT a
    trailing window: anchoring to the long history is what keeps a sustained collapse
    (the Strait of Hormuz at ~6/day for months) reading as stressed, rather than the
    "normal" silently converging to the collapsed level once it fills the window — the
    whole Hormuz lesson, and what makes the live index agree with the 2019->now history
    view. The long-window normal + capacity weight are supplied by the exporter (it has
    the full DB); compute() falls back to the window percentile + count weight only for
    bare-values callers (synthetic tests).
  - Each chokepoint's daily STRESS s_i(t) in [0,1] = how far its level sits from its
    own normal: squash(|value - normal| / normal), floored at 15% (ignore daily
    wiggle) and saturated at 100% deviation. Deviation is measured vs the *normal*
    (not a trailing mean) so a level-shift that the rolling baseline has adapted to
    still reads as stressed. Each s_i is smoothed over a 3-day trailing window so a
    one-day blip can't spike the index but a sustained shift survives.
  - The index BLENDS breadth and depth:
        breadth(t) = Σ_i weight_i · s_i(t)   (how broadly the system is stressed)
        depth(t)   = max_i s_i(t)            (how bad the single worst chokepoint is)
        index(t)   = 100 · (0.6·breadth + 0.4·depth)
    The depth term is deliberate: a pure economic-weighted mean averages a single
    strategic-strait crisis (Hormuz, Suez-2021) down to "calm" because 27 other
    lanes flow normally. The 40% depth weight keeps a concentrated collapse visible
    in the headline without making a calm system read as stressed. Both raw
    components are exposed in the payload so the blend is fully inspectable.
  - Recomputed for every day in the window so the sparkline + week-over-week
    momentum are real history, not a snapshot.

This is a transparent index, not a market instrument — labelled as such in the UI.
"""

from __future__ import annotations

import json
from pathlib import Path

# Tunables (documented; echoed into stress.json so the method is self-describing).
NORMAL_PCTILE = 0.80      # "normal" throughput = 80th pct of the window
DEV_FLOOR = 0.15          # ignore deviations under 15% (daily noise)
DEV_SATURATE = 1.00       # a 100% deviation = max single-chokepoint stress
SMOOTH_DAYS = 3           # trailing-day smoothing of each s_i (kill one-day blips)
BREADTH_W = 0.60          # weight on economic-weighted breadth
DEPTH_W = 0.40            # weight on the single worst chokepoint (depth)
DISRUPTED_AT = 0.30       # a chokepoint counts as "disrupted" at s_i >= 0.30
MOMENTUM_WINDOW = 7       # week-over-week comparison window (days)
MOVER_WINDOW = 14         # lookback for fastest-deteriorating / most-improved


def _pctile(values: list[float], q: float) -> float:
    """Linear-interpolation percentile (no numpy dependency)."""
    xs = sorted(v for v in values if v is not None)
    if not xs:
        return 0.0
    if len(xs) == 1:
        return float(xs[0])
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return float(xs[lo] * (1 - frac) + xs[hi] * frac)


def _stress(value: float, normal: float) -> float:
    """Squash a chokepoint's deviation-from-normal into [0,1]."""
    if normal <= 0:
        return 0.0
    dev = abs(value - normal) / normal
    if dev <= DEV_FLOOR:
        return 0.0
    return min(1.0, (dev - DEV_FLOOR) / (DEV_SATURATE - DEV_FLOOR))


def _smooth(xs: list[float]) -> list[float]:
    """Trailing SMOOTH_DAYS-day mean of a series (causal — no future leakage)."""
    out = []
    for t in range(len(xs)):
        lo = max(0, t - SMOOTH_DAYS + 1)
        win = xs[lo:t + 1]
        out.append(sum(win) / len(win))
    return out


def _label(index: float) -> str:
    # calibrated to the blended breadth+depth scale: a single strategic strait
    # fully collapsed lands ~40 ("high"); a quiet system sits in the single digits.
    if index >= 55:
        return "severe"
    if index >= 35:
        return "high"
    if index >= 15:
        return "elevated"
    return "calm"


def compute(timeseries: dict) -> dict:
    """Compute the stress index + history + momentum from a timeseries payload."""
    dates: list[str] = timeseries.get("dates", [])
    chokes: list[dict] = timeseries.get("chokepoints", [])
    if not dates or not chokes:
        return {"available": False}

    n_days = len(dates)
    # "normal" throughput, anchored to the chokepoint's FULL record so a sustained
    # collapse keeps driving the index: the exporter supplies it (`normal`, computed
    # over the whole DB history); we fall back to the window percentile only for
    # bare-values callers (synthetic tests).
    normals = {
        c["portid"]: (c["normal"] if c.get("normal") is not None
                      else _pctile(c.get("values", []), NORMAL_PCTILE))
        for c in chokes
    }
    # economic weight = normal vessel-CAPACITY (DWT) share when supplied (`cap_normal`,
    # also a full-history 80th-pct), else fall back to the count-based normal share.
    cap_basis = {
        c["portid"]: (c["cap_normal"] if c.get("cap_normal") is not None
                      else normals[c["portid"]])
        for c in chokes
    }
    total_cap = sum(cap_basis.values()) or 1.0
    weights = {pid: cv / total_cap for pid, cv in cap_basis.items()}
    meta = {c["portid"]: c for c in chokes}

    # raw per-chokepoint stress for every day, then causal 3-day smoothing
    per_choke_s: dict[str, list[float]] = {}
    for c in chokes:
        pid = c["portid"]
        vals = c.get("values", [])
        raw = [_stress(float(vals[t]) if t < len(vals) and vals[t] is not None else 0.0,
                       normals[pid]) for t in range(n_days)]
        per_choke_s[pid] = _smooth(raw)

    # per-day index = blend of economic-weighted breadth and worst-chokepoint depth
    history, breadth_hist, depth_hist = [], [], []
    for t in range(n_days):
        breadth = sum(weights[pid] * per_choke_s[pid][t] for pid in normals)
        depth = max(per_choke_s[pid][t] for pid in normals)
        breadth_hist.append(breadth)
        depth_hist.append(depth)
        history.append(round(100 * (BREADTH_W * breadth + DEPTH_W * depth), 1))

    current = history[-1]

    # week-over-week momentum (mean of last 7 vs prior 7)
    def _mean(xs):
        return sum(xs) / len(xs) if xs else 0.0
    last_wk = _mean(history[-MOMENTUM_WINDOW:])
    prev_wk = _mean(history[-2 * MOMENTUM_WINDOW:-MOMENTUM_WINDOW])
    wow = round(last_wk - prev_wk, 1)

    # how many of the 28 are disrupted right now + the daily history (for a trend)
    disrupted = [pid for pid in normals if per_choke_s[pid][-1] >= DISRUPTED_AT]
    disrupted_history = [sum(1 for pid in normals if per_choke_s[pid][t] >= DISRUPTED_AT)
                         for t in range(n_days)]

    # current contributors: who is driving the index today (weight * stress)
    contributors = []
    for pid, w in weights.items():
        s_now = per_choke_s[pid][-1]
        if s_now <= 0:
            continue
        c = meta[pid]
        vals = c.get("values", [])
        contributors.append({
            "portid": pid,
            "name": c.get("name"),
            "lat": c.get("lat"),
            "lon": c.get("lon"),
            "weight": round(w, 4),
            "stress": round(s_now, 3),
            "contribution": round(100 * w * s_now, 2),
            "now": round(float(vals[-1]), 1) if vals else None,
            "normal": round(normals[pid], 1),
            "pct_vs_normal": round((float(vals[-1]) - normals[pid]) / normals[pid] * 100, 1)
            if vals and normals[pid] else None,
        })
    contributors.sort(key=lambda x: x["contribution"], reverse=True)

    # momentum movers: change in s_i over the MOVER_WINDOW
    movers = []
    w0 = max(0, n_days - 1 - MOVER_WINDOW)
    for pid in normals:
        s_then = per_choke_s[pid][w0]
        s_now = per_choke_s[pid][-1]
        delta = s_now - s_then
        if abs(delta) < 0.05:
            continue
        c = meta[pid]
        movers.append({
            "portid": pid, "name": c.get("name"),
            "delta_stress": round(delta, 3),
            "direction": "deteriorating" if delta > 0 else "improving",
            "days": MOVER_WINDOW,
        })
    movers.sort(key=lambda x: x["delta_stress"])
    most_improved = movers[0] if movers and movers[0]["delta_stress"] < 0 else None
    fastest_deteriorating = movers[-1] if movers and movers[-1]["delta_stress"] > 0 else None

    # a 30-day tail for the sparkline (full history kept for the chat/brief)
    spark = history[-30:]

    return {
        "available": True,
        "index": current,
        "label": _label(current),
        "breadth": round(100 * breadth_hist[-1], 1),
        "depth": round(100 * depth_hist[-1], 1),
        "as_of": dates[-1],
        "wow_delta": wow,
        "wow_direction": "up" if wow > 0.5 else "down" if wow < -0.5 else "flat",
        "chokepoints_total": len(chokes),
        "chokepoints_disrupted": len(disrupted),
        "disrupted_history": disrupted_history,
        "history": history,
        "history_dates": dates,
        "spark30": spark,
        "contributors": contributors[:6],
        "fastest_deteriorating": fastest_deteriorating,
        "most_improved": most_improved,
        "method": (
            "Capacity-weighted (DWT share) mean of per-chokepoint deviation from "
            "normal throughput, blended with the worst single chokepoint (0.6 breadth "
            "/ 0.4 depth). Normal = 80th-pct of each chokepoint's full PortWatch record "
            "(2019->now), so a sustained collapse keeps driving the index; 0-100, daily."
        ),
        "source": "IMF PortWatch — daily granularity, refreshed weekly",
    }


def run(ctx) -> dict:
    """Enricher entrypoint: read timeseries.json, write stress.json."""
    out = Path(ctx.out_dir)
    ts_path = out / "timeseries.json"
    if not ts_path.exists():
        return {"name": "stress", "error": "timeseries.json missing"}
    ts = json.loads(ts_path.read_text())
    payload = compute(ts)
    payload["generated_at"] = ctx.today
    (out / "stress.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "stress", "sidecar": "stress.json",
            "index": payload.get("index"), "label": payload.get("label")}


if __name__ == "__main__":
    import sys
    from ..config import publish_dir
    ts = json.loads((publish_dir() / "timeseries.json").read_text())
    out = compute(ts)
    json.dump({k: v for k, v in out.items() if k not in ("history", "history_dates")},
              sys.stdout, indent=2)
