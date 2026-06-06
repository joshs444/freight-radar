"""Earthquake layer (USGS) -> quakes.json for the globe dots.

One dot per M4.0+ earthquake observed in the past 7 days, sized by magnitude, click
opens the USGS event page. The safest possible context layer: USGS all_week is
public-domain, keyless, and records observed seismic events — there is no honest way to
read it as a model output. It is CONTEXT only: a co-located, co-timed physical event the
reader can weigh near a flagged port, never a stated cause of any freight number, and
it carries no computed metric.

Sidecar-only via the enricher registry (like gdelt_news / wind) — it never reads the DB
or writes the flags file, so a quake can structurally never move a number. Degrades to
no layer on any failure. Source: USGS Earthquake Hazards Program — US-government public
domain. Free, keyless.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from . import _http

log = logging.getLogger(__name__)

FEED = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson"
MIN_MAG = 4.0
CAP = 500

SOURCE = "USGS Earthquakes — M4.0+ over the past 7 days (observed)"
SOURCE_URL = "https://earthquake.usgs.gov/earthquakes/map/"
# Honest framing — a fact the reader weighs, not a verdict or a claim about cause.
DISCLAIMER = ("A co-located, co-timed seismic event (M4.0+) the reader can weigh near a "
              "place — never a stated cause of a freight number. Click to open the USGS "
              "event page.")


def _fmt_time(ms) -> str:
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    except (TypeError, ValueError, OSError):
        return ""


def _collect() -> list[dict]:
    with _http.client(timeout=25.0) as c:
        r = _http.get(c, FEED)
        r.raise_for_status()
        feats = r.json().get("features", [])
    items: list[dict] = []
    for f in feats:
        p = f.get("properties", {}) or {}
        g = (f.get("geometry") or {}).get("coordinates") or []
        mag = p.get("mag")
        if mag is None or mag < MIN_MAG or len(g) < 2:
            continue
        lon, lat = g[0], g[1]
        if lon is None or lat is None:
            continue
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        items.append({
            "id": f.get("id"),
            "mag": round(float(mag), 1),
            "place": p.get("place") or "",
            "lat": round(lat, 3), "lon": round(lon, 3),
            "depth_km": round(float(g[2]), 1) if len(g) > 2 and g[2] is not None else None,
            "time": _fmt_time(p.get("time")),
            "tsunami": bool(p.get("tsunami")),
            "url": p.get("url") or "",
        })
    items.sort(key=lambda x: x["mag"], reverse=True)
    return items[:CAP]


def run(ctx) -> dict:
    out = Path(ctx.out_dir)
    try:
        items = _collect()
    except Exception as exc:  # noqa: BLE001 — degrade: the frontend hides an absent layer
        log.warning("quakes layer unavailable this run: %r", exc)
        return {"name": "quakes", "sidecar": "quakes.json", "error": repr(exc)}
    if not items:
        return {"name": "quakes", "sidecar": "quakes.json", "error": "no M4+ events in window"}

    payload = {
        "generated_at": ctx.today,
        "as_of": getattr(ctx, "as_of", None) or ctx.today,
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "disclaimer": DISCLAIMER,
        "min_mag": MIN_MAG,
        "counts": {"total": len(items), "m5plus": sum(1 for i in items if i["mag"] >= 5.0)},
        "items": items,
    }
    (out / "quakes.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "quakes", "sidecar": "quakes.json", "count": len(items),
            "m5plus": payload["counts"]["m5plus"]}


if __name__ == "__main__":
    import types
    from datetime import date

    from ._log import configure as configure_logging
    from .config import publish_dir

    configure_logging()
    ctx = types.SimpleNamespace(out_dir=publish_dir(), as_of=date.today().isoformat(),
                                today=date.today().isoformat())
    print(run(ctx))
