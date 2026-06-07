"""Space weather — a cited CONTEXT layer (P4).

Geomagnetic storms degrade GPS positioning, HF radio (used by aviation + maritime), and
satellite operations — the navigation/comms backdrop to global logistics. We show NOAA
SWPC's **observed** planetary K-index + the current R/S/G storm scales exactly as published
(CONTEXT, association-only) — observed values only, never a stated cause. Keyless,
public-domain SWPC JSON; degrades to absent on any failure.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from . import _http

log = logging.getLogger(__name__)

_KP_URL = "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json"
_SCALES_URL = "https://services.swpc.noaa.gov/products/noaa-scales.json"
_SRC = "NOAA SWPC — observed planetary K-index + space-weather scales"
_SRC_URL = "https://www.swpc.noaa.gov"
_DISCLAIMER = (
    "NOAA SWPC observed values, shown as published — a cited reading the reader weighs. "
    "Geomagnetic activity can degrade GPS/HF-radio/satellite ops; possibly-related context, "
    "never a stated cause."
)
# the SWPC G-scale labels (geomagnetic storm severity), G0 = quiet
_G_LABEL = {"0": "quiet", "1": "minor", "2": "moderate", "3": "strong", "4": "severe", "5": "extreme"}


def parse_kp(rows: list[dict]) -> list[dict]:
    """SWPC planetary-K-index rows -> the trailing readings (time, kp)."""
    out: list[dict] = []
    for r in rows:
        t = r.get("time_tag")
        kp = r.get("Kp")
        if t is None or kp is None:
            continue
        try:
            out.append({"time": str(t), "kp": round(float(kp), 2)})
        except (TypeError, ValueError):
            continue
    return out


def _scale(block: dict, key: str) -> dict:
    s = (block or {}).get(key) or {}
    return {"level": str(s.get("Scale", "0")), "text": s.get("Text") or "none"}


def compute(kp_rows: list[dict], scales: dict) -> dict | None:
    """Build the observed-space-weather snapshot from the two SWPC feeds."""
    series = parse_kp(kp_rows)
    if not series:
        return None
    series = series[-16:]  # ~48h of 3-hourly readings
    kp_vals = [r["kp"] for r in series]
    current = (scales or {}).get("0") or {}
    g = _scale(current, "G")
    return {
        "as_of": series[-1]["time"][:10],
        "source": _SRC,
        "source_url": _SRC_URL,
        "disclaimer": _DISCLAIMER,
        "kp_now": kp_vals[-1],
        "kp_max_48h": max(kp_vals),
        "geomagnetic_storm": {"scale": "G" + g["level"], "label": _G_LABEL.get(g["level"], g["text"])},
        "scales": {
            "R_radio_blackout": _scale(current, "R"),
            "S_solar_radiation": _scale(current, "S"),
            "G_geomagnetic": g,
        },
        "counts": {"readings": len(series)},
        "items": series,
    }


def run(ctx) -> dict:
    """Enricher entrypoint: fetch SWPC, write space_weather.json (CONTEXT)."""
    try:
        with _http.client(timeout=20.0) as c:
            kp = _http.get(c, _KP_URL)
            kp.raise_for_status()
            try:
                scales = _http.get(c, _SCALES_URL).json()
            except Exception:  # noqa: BLE001 — scales optional; Kp alone still yields a layer
                scales = {}
            payload = compute(kp.json(), scales)
    except Exception as e:  # noqa: BLE001 — degrade to absent (offline / CI)
        return {"name": "space_weather", "sidecar": "space_weather.json", "error": repr(e)}

    if payload is None:
        return {"name": "space_weather", "sidecar": "space_weather.json", "error": "no Kp data"}
    payload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (ctx.out_dir / "space_weather.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {
        "name": "space_weather",
        "sidecar": "space_weather.json",
        "kp_now": payload["kp_now"],
        "storm": payload["geomagnetic_storm"]["scale"],
    }
