"""Coastal water level at major US ports — a cited CONTEXT layer (P4).

NOAA CO-OPS publishes the observed water level (vs the MLLW datum) at tide stations, keyless.
At the major US container ports it is the tidal access backdrop — draft windows for the
deepest-draft calls track the tide. We show the observed level as NOAA publishes it (CONTEXT,
association-only) — never a stated cause. The coastal complement to the inland river-stage
layer. Degrades to absent (per-station + overall) on any failure.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from . import _http

log = logging.getLogger(__name__)

# Major US container ports (name, CO-OPS station id, lat, lon).
PORTS: tuple[tuple[str, str, float, float], ...] = (
    ("Los Angeles", "9410660", 33.72, -118.27),
    ("Long Beach", "9410680", 33.77, -118.19),
    ("New York/NJ", "8518750", 40.70, -74.01),
    ("Savannah", "8670870", 32.03, -80.90),
    ("Seattle", "9447130", 47.60, -122.34),
    ("San Francisco", "9414290", 37.81, -122.47),
    ("Charleston", "8665530", 32.78, -79.92),
    ("Virginia (Sewells Pt)", "8638610", 36.95, -76.33),
)

_BASE = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
_SRC = "NOAA CO-OPS — observed water level (datum MLLW)"
_SRC_URL = "https://tidesandcurrents.noaa.gov"
_DISCLAIMER = (
    "Observed water level at the port as NOAA CO-OPS publishes it — a cited reading the reader "
    "weighs. Tides set draft windows; shown as possibly-related context, never a stated cause."
)
_UA = "freight-radar/0.1 (+portfolio)"


def _level(payload: dict) -> float | None:
    data = (payload or {}).get("data") or []
    if not data:
        return None
    try:
        return round(float(data[-1].get("v")), 2)
    except (TypeError, ValueError):
        return None


def run(ctx) -> dict:
    items: list[dict] = []
    try:
        with _http.client(headers={"User-Agent": _UA}, timeout=20.0) as c:
            for name, station, lat, lon in PORTS:
                try:
                    url = (
                        f"{_BASE}?product=water_level&station={station}&date=latest"
                        "&datum=MLLW&format=json&units=english&time_zone=gmt"
                    )
                    payload = _http.get(c, url).json()
                    level = _level(payload)
                    if level is None:
                        continue
                    items.append(
                        {
                            "port": name,
                            "station": station,
                            "lat": lat,
                            "lon": lon,
                            "water_level_ft": level,
                            "observed_at": (payload["data"][-1].get("t", "")),
                            "url": f"https://tidesandcurrents.noaa.gov/stationhome.html?id={station}",
                        }
                    )
                except Exception as e:  # noqa: BLE001 — one bad station never sinks the layer
                    log.warning("tides: %s failed: %r", station, e)
    except Exception as e:  # noqa: BLE001 — degrade to absent (offline / CI)
        return {"name": "tides", "sidecar": "tides.json", "error": repr(e)}

    if not items:
        return {"name": "tides", "sidecar": "tides.json", "error": "no stations"}
    items.sort(key=lambda i: i["port"])
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": max((i["observed_at"][:10] for i in items), default=""),
        "source": _SRC,
        "source_url": _SRC_URL,
        "disclaimer": _DISCLAIMER,
        "counts": {"ports": len(items)},
        "items": items,
    }
    (ctx.out_dir / "tides.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "tides", "sidecar": "tides.json", "ports": len(items)}
