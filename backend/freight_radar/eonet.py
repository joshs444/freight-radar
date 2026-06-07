"""Natural-event tracker — a cited CONTEXT layer (P4).

NASA EONET (Earth Observatory Natural Event Tracker) curates *currently open* natural
events worldwide — wildfires, volcanoes, severe storms, sea/lake ice — each geo-located
and source-linked. One feed covers four hazard domains that can shutter ports, close air
corridors, or block shipping lanes. We show the **observed events as NASA tracks them** —
cited, possibly-related context, never a stated cause. Keyless, public-domain; degrades to
absent on any failure.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from . import _http

log = logging.getLogger(__name__)

_URL = "https://eonet.gsfc.nasa.gov/api/v3/events?status=open&limit=300"
_SRC = "NASA EONET — Earth Observatory Natural Event Tracker (observed, open events)"
_SRC_URL = "https://eonet.gsfc.nasa.gov"
_DISCLAIMER = (
    "Currently-open natural events as NASA EONET tracks them — cited, possibly-related "
    "context the reader weighs, never a stated cause of a freight movement."
)
_CAP = 250


def parse(events: list[dict]) -> list[dict]:
    """EONET v3 events -> one item per event at its latest point location."""
    items: list[dict] = []
    for e in events:
        geoms = e.get("geometry") or []
        pt = next((g for g in reversed(geoms) if g.get("type") == "Point"), None)
        if not pt:
            continue
        coords = pt.get("coordinates") or []
        if len(coords) < 2:
            continue
        cats = e.get("categories") or [{}]
        src = e.get("sources") or [{}]
        items.append(
            {
                "id": e.get("id"),
                "title": e.get("title"),
                "category": cats[0].get("title") or "Event",
                "lat": float(coords[1]),
                "lon": float(coords[0]),
                "date": pt.get("date", ""),
                "url": e.get("link") or src[0].get("url") or _SRC_URL,
            }
        )
    items.sort(key=lambda i: i["date"], reverse=True)
    return items[:_CAP]


def run(ctx) -> dict:
    """Enricher entrypoint: fetch EONET open events, write eonet.json (CONTEXT)."""
    try:
        with _http.client(timeout=25.0) as c:
            r = _http.get(c, _URL)
            r.raise_for_status()
            items = parse(r.json().get("events", []))
    except Exception as e:  # noqa: BLE001 — degrade to absent (offline / CI)
        return {"name": "eonet", "sidecar": "eonet.json", "error": repr(e)}

    if not items:
        return {"name": "eonet", "sidecar": "eonet.json", "error": "no events"}
    from collections import Counter

    by_cat = Counter(i["category"] for i in items)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": max((i["date"][:10] for i in items), default=""),
        "source": _SRC,
        "source_url": _SRC_URL,
        "disclaimer": _DISCLAIMER,
        "counts": {"events": len(items), "by_category": dict(by_cat)},
        "items": items,
    }
    (ctx.out_dir / "eonet.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "eonet", "sidecar": "eonet.json", "events": len(items)}
