"""Marine conditions — a cited CONTEXT layer (P4).

Open-Meteo's marine model reports current significant wave height at a point, keyless. We
show it at the world's major maritime chokepoints — rough seas slow transits and force
reroutes, the sea-state backdrop to the freight spine. Shown as the model reports it
(CONTEXT, association-only) — never a stated cause. Inland canals (Suez/Panama/Bosphorus)
return no open-water wave height and simply drop out. Degrades to absent on any failure.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from . import _http

log = logging.getLogger(__name__)

# Major maritime chokepoints (name, lat, lon). Open-water straits report wave height;
# the canals among them return none and are skipped.
CHOKEPOINTS: tuple[tuple[str, float, float], ...] = (
    ("Strait of Hormuz", 26.5, 56.2),
    ("Strait of Malacca", 2.5, 101.3),
    ("Singapore Strait", 1.2, 103.8),
    ("Bab-el-Mandeb", 12.6, 43.4),
    ("Strait of Gibraltar", 35.95, -5.6),
    ("Dover Strait", 51.0, 1.5),
    ("Taiwan Strait", 24.5, 119.5),
    ("Cape of Good Hope", -34.8, 19.5),
    ("Strait of Magellan", -53.5, -70.5),
    ("Tsugaru Strait", 41.5, 140.5),
    ("Luzon Strait", 20.5, 121.0),
    ("Mozambique Channel", -18.0, 41.0),
)

_BASE = "https://marine-api.open-meteo.com/v1/marine"
_SRC = "Open-Meteo marine model — significant wave height (current)"
_SRC_URL = "https://open-meteo.com"
_DISCLAIMER = (
    "Open-Meteo marine model wave height at major chokepoints, shown as the model reports it "
    "— possibly-related context the reader weighs, never a stated cause. Rough seas slow transits."
)


def parse(records: list[dict]) -> list[dict]:
    """Open-Meteo marine records (one per chokepoint, input order) -> items with wave height."""
    items: list[dict] = []
    for (name, lat, lon), rec in zip(CHOKEPOINTS, records):
        cur = (rec or {}).get("current") or {}
        wh = cur.get("wave_height")
        if wh is None:
            continue
        try:
            wave = float(wh)
        except (TypeError, ValueError):
            continue
        items.append(
            {
                "name": name,
                "lat": lat,
                "lon": lon,
                "wave_height_m": round(wave, 2),
                "wave_period_s": cur.get("wave_period"),
                "observed_at": cur.get("time", ""),
            }
        )
    items.sort(key=lambda i: i["wave_height_m"], reverse=True)
    return items


def run(ctx) -> dict:
    """Enricher entrypoint: fetch marine wave height at the chokepoints, write marine.json."""
    lats = ",".join(str(c[1]) for c in CHOKEPOINTS)
    lons = ",".join(str(c[2]) for c in CHOKEPOINTS)
    url = f"{_BASE}?latitude={lats}&longitude={lons}&current=wave_height,wave_period"
    try:
        with _http.client(timeout=25.0) as c:
            r = _http.get(c, url)
            r.raise_for_status()
            data = r.json()
            records = data if isinstance(data, list) else [data]
            items = parse(records)
    except Exception as e:  # noqa: BLE001 — degrade to absent (offline / CI)
        return {"name": "marine", "sidecar": "marine.json", "error": repr(e)}

    if not items:
        return {"name": "marine", "sidecar": "marine.json", "error": "no wave data"}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": max((i["observed_at"][:10] for i in items), default=""),
        "source": _SRC,
        "source_url": _SRC_URL,
        "disclaimer": _DISCLAIMER,
        "counts": {"chokepoints": len(items)},
        "items": items,
    }
    (ctx.out_dir / "marine.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "marine", "sidecar": "marine.json", "chokepoints": len(items)}
