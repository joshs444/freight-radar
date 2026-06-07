"""Inland-waterway river stage — a cited CONTEXT layer (P4).

The inland-freight analog of the Panama/Gatún draft signal: gage height on the major
US river-freight corridor (Mississippi + Ohio). Low water → barge draft restrictions and
load limits, a real disruption signal for the ~$80B/yr that moves on these rivers. We show
the **observed stage as USGS publishes it** — a cited reading the reader weighs, never a
"low water caused X" claim (CONTEXT, association-only). Keyless USGS Water Services JSON;
degrades to absent on any failure.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from . import _http

log = logging.getLogger(__name__)

# Curated, verified gage-height stations (USGS param 00065) on the Mississippi/Ohio
# freight corridor. Each id is a real, active station that publishes stage; the layer
# degrades gracefully if any one stops reporting.
GAUGES: tuple[tuple[str, str, str], ...] = (
    ("05420500", "Upper Mississippi", "Clinton, IA"),
    ("07010000", "Mississippi", "St. Louis, MO"),
    ("07022000", "Mississippi", "Thebes, IL"),
    ("03612600", "Ohio", "Olmsted, IL"),
    ("07374000", "Lower Mississippi", "Baton Rouge, LA"),
)

_BASE = "https://waterservices.usgs.gov/nwis/iv/"
_SRC = "USGS Water Services — instantaneous gage height (observed)"
_SRC_URL = "https://waterservices.usgs.gov"
_DISCLAIMER = (
    "Observed river stage as published by USGS — a cited reading the reader weighs. Low water "
    "can restrict barge drafts; shown as possibly-related context, never a stated cause."
)


def parse(payload: dict) -> list[dict]:
    """USGS Water Services JSON -> one item per gauge with lat/lon + latest stage."""
    by_site = {g[0]: (g[1], g[2]) for g in GAUGES}
    items: list[dict] = []
    for s in payload.get("value", {}).get("timeSeries", []):
        info = s.get("sourceInfo", {})
        sid = (info.get("siteCode") or [{}])[0].get("value")
        vals = (s.get("values") or [{}])[0].get("value") or []
        if not sid or sid not in by_site or not vals:
            continue
        latest = vals[-1]
        try:
            stage = float(latest.get("value"))
        except (TypeError, ValueError):
            continue
        if stage <= -999990:  # USGS missing-data sentinel
            continue
        geo = info.get("geoLocation", {}).get("geogLocation", {})
        river, place = by_site[sid]
        items.append(
            {
                "site": sid,
                "river": river,
                "place": place,
                "lat": float(geo.get("latitude")),
                "lon": float(geo.get("longitude")),
                "stage_ft": round(stage, 2),
                "observed_at": latest.get("dateTime", ""),
                "url": f"https://waterdata.usgs.gov/monitoring-location/{sid}/",
            }
        )
    items.sort(key=lambda i: (i["river"], i["place"]))
    return items


def run(ctx) -> dict:
    """Enricher entrypoint: fetch the curated gauges, write streamflow.json (CONTEXT)."""
    sites = ",".join(g[0] for g in GAUGES)
    url = f"{_BASE}?format=json&sites={sites}&parameterCd=00065&siteStatus=active"
    try:
        with _http.client(timeout=25.0) as c:
            r = _http.get(c, url)
            r.raise_for_status()
            items = parse(r.json())
    except Exception as e:  # noqa: BLE001 — degrade to absent (offline / CI)
        return {"name": "streamflow", "sidecar": "streamflow.json", "error": repr(e)}

    if not items:
        return {"name": "streamflow", "sidecar": "streamflow.json", "error": "no gauges"}
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "as_of": max((i["observed_at"][:10] for i in items), default=""),
        "source": _SRC,
        "source_url": _SRC_URL,
        "disclaimer": _DISCLAIMER,
        "counts": {"gauges": len(items)},
        "items": items,
    }
    (ctx.out_dir / "streamflow.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "streamflow", "sidecar": "streamflow.json", "gauges": len(items)}
