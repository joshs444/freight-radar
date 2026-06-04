"""Live tropical-cyclone layer (Phase C1) — ACTIVE storms from NHC + GDACS, matched
by proximity to flagged ports/chokepoints as a *possibly related* physical driver.

Distinct from hazards.py: that surfaces curated *historical* GDACS events (with the
exact affected port IDs) via IMF PortWatch and has no live forecast. This fetches the
LIVE active-storm feeds and attaches the nearest one to a flag's entity:

  - NHC CurrentStorms.json — Atlantic + E/Central Pacific (the official US cone).
  - GDACS geteventlist SEARCH?eventlist=TC — every basin, so it covers the W Pacific
    + Indian Ocean systems (Malacca / Hormuz / Taiwan / Luzon) that NHC never issues.

Dedup: GDACS also lists the NHC basins (source == 'NOAA'); we DROP those and keep NHC
as authoritative, so a storm is never double-counted. Honesty: a storm near a flagged
port is labelled "possibly related" with its distance — never "caused". Off-season the
feeds are empty and the layer simply reports zero active storms.

CORS: NHC's JSON sends no Access-Control-Allow-Origin, so it MUST be fetched here at
publish time and shipped as weather.json — the browser never calls these APIs.
Sources: NOAA/NHC (nhc.noaa.gov) + GDACS (gdacs.org) — free, keyless.
"""

from __future__ import annotations

import json
import math
from datetime import date
from pathlib import Path

import httpx

NHC_URL = "https://www.nhc.noaa.gov/CurrentStorms.json"
GDACS_URL = "https://www.gdacs.org/gdacsapi/api/events/geteventlist/SEARCH?eventlist=TC"
MATCH_RADIUS_KM = 500  # a TC's influence is broad; within this of a flag = "possibly related"
KT_TO_KMH = 1.852
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"

# NHC storm-id prefix -> basin label.
_NHC_BASIN = {"al": "N Atlantic", "ep": "E Pacific", "cp": "C Pacific"}
# NHC classification code -> human label.
_NHC_CLASS = {
    "HU": "Hurricane", "TS": "Tropical Storm", "TD": "Tropical Depression",
    "STS": "Severe Tropical Storm", "SD": "Subtropical Depression",
    "SS": "Subtropical Storm", "PTC": "Potential Tropical Cyclone",
    "EX": "Post-Tropical", "LO": "Low", "DB": "Disturbance",
}


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize_nhc(raw: dict) -> list[dict]:
    """NHC activeStorms[] -> common storm dicts. latitudeNumeric/longitudeNumeric are
    signed floats (use them, not the N/S/E/W strings)."""
    out = []
    for s in raw.get("activeStorms", []) or []:
        lat, lon = _num(s.get("latitudeNumeric")), _num(s.get("longitudeNumeric"))
        if lat is None or lon is None:
            continue
        kt = _num(s.get("intensity"))
        sid = str(s.get("id", ""))
        cone = (s.get("trackCone") or {}).get("kmzFile") or (s.get("trackCone") or {}).get("zipFile")
        out.append({
            "id": sid or s.get("name"),
            "name": s.get("name"),
            "category": _NHC_CLASS.get(s.get("classification"), s.get("classification")),
            "basin": _NHC_BASIN.get(sid[:2].lower(), "Pacific/Atlantic"),
            "lat": round(lat, 2), "lon": round(lon, 2),
            "source": "NHC", "agency": "NHC",
            "max_wind_kmh": round(kt * KT_TO_KMH) if kt is not None else None,
            "advisory": (s.get("trackCone") or {}).get("issuance") or s.get("lastUpdate"),
            "cone_url": cone,
            "url": f"https://www.nhc.noaa.gov/refresh/graphics_{sid[:2].lower()}1+shtml/" if sid else None,
        })
    return out


def normalize_gdacs(raw: dict) -> list[dict]:
    """GDACS TC FeatureCollection -> common storm dicts, dropping NHC-basin duplicates
    (properties.source == 'NOAA') so NHC stays authoritative. Keeps the JTWC/RSMC
    W-Pacific + Indian-Ocean systems NHC never covers."""
    out = []
    for f in raw.get("features", []) or []:
        p = f.get("properties", {}) or {}
        if str(p.get("eventtype")) != "TC":
            continue
        if str(p.get("iscurrent")).lower() != "true":   # only active systems
            continue
        if str(p.get("source", "")).upper() == "NOAA":   # NHC duplicate — drop
            continue
        coords = (f.get("geometry") or {}).get("coordinates") or [None, None]
        lon, lat = _num(coords[0]), _num(coords[1])
        if lat is None or lon is None:
            continue
        sev = (p.get("severitydata") or {}).get("severity")
        name = str(p.get("eventname") or "").rsplit("-", 1)[0] or p.get("eventname")
        urls = p.get("url") or {}
        out.append({
            "id": f"gdacs-{p.get('eventid')}",
            "name": name,
            "category": "Tropical Cyclone",
            "basin": _gdacs_basin(p.get("source")),
            "lat": round(lat, 2), "lon": round(lon, 2),
            "source": "GDACS", "agency": str(p.get("source") or "GDACS"),
            "alertlevel": str(p.get("alertlevel") or "").upper() or None,
            "max_wind_kmh": round(_num(sev)) if _num(sev) is not None else None,
            "advisory": p.get("datemodified") or p.get("todate"),
            "cone_url": urls.get("geometry"),
            "url": urls.get("report"),
        })
    return out


def _gdacs_basin(source) -> str:
    return {"JTWC": "W Pacific / Indian", "RSMC": "S Indian"}.get(str(source or "").upper(), "Global")


def fetch_storms(client: httpx.Client | None = None) -> list[dict]:
    """Both live feeds, normalized + merged. A failed feed degrades to [] for that
    source (never aborts) — the other still publishes."""
    own = client is None
    client = client or httpx.Client(timeout=20.0, headers={"User-Agent": BROWSER_UA},
                                    follow_redirects=True)
    storms: list[dict] = []
    try:
        for url, norm in ((NHC_URL, normalize_nhc), (GDACS_URL, normalize_gdacs)):
            try:
                r = client.get(url)
                r.raise_for_status()
                storms += norm(r.json())
            except (httpx.HTTPError, ValueError):
                continue
    finally:
        if own:
            client.close()
    return storms


def attach_storms(flags: list[dict], storms: list[dict]) -> int:
    """Set `live_storm` on each non-resolved flag whose entity sits within
    MATCH_RADIUS_KM of an active storm's centre (nearest wins). Returns match count."""
    n = 0
    for f in flags:
        if f.get("lifecycle") == "resolved":
            f.pop("live_storm", None)
            continue
        lat, lon = _num(f.get("lat")), _num(f.get("lon"))
        if lat is None or lon is None:
            f.pop("live_storm", None)
            continue
        best, best_km = None, MATCH_RADIUS_KM
        for s in storms:
            km = _haversine_km(lat, lon, s["lat"], s["lon"])
            if km <= best_km:
                best, best_km = s, km
        if best:
            f["live_storm"] = {
                "name": best["name"], "category": best["category"], "basin": best["basin"],
                "agency": best["agency"], "source": best["source"],
                "km": round(best_km), "max_wind_kmh": best.get("max_wind_kmh"),
                "url": best.get("url"), "cone_url": best.get("cone_url"),
            }
            n += 1
        else:
            f.pop("live_storm", None)
    return n


def run(ctx) -> dict:
    out = Path(ctx.out_dir)
    storms = fetch_storms()
    flags_path = Path(ctx.flags_path)
    matched = 0
    if flags_path.exists():
        flags = json.loads(flags_path.read_text())
        matched = attach_storms(flags, storms)
        flags_path.write_text(json.dumps(flags, indent=2))
    payload = {
        "generated_at": ctx.today,
        "as_of": ctx.as_of or date.today().isoformat(),
        "source": "NOAA/NHC CurrentStorms + GDACS active tropical cyclones (live forecast positions)",
        "match_radius_km": MATCH_RADIUS_KM,
        "storms": sorted(storms, key=lambda s: s["name"] or ""),
        "counts": {"active_storms": len(storms),
                   "nhc": sum(1 for s in storms if s["source"] == "NHC"),
                   "gdacs": sum(1 for s in storms if s["source"] == "GDACS"),
                   "flags_matched": matched},
    }
    (out / "weather.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "weather", "sidecar": "weather.json",
            "active_storms": len(storms), "matched": matched}


if __name__ == "__main__":
    storms = fetch_storms()
    print(f"active storms: {len(storms)} "
          f"(NHC={sum(1 for s in storms if s['source']=='NHC')}, "
          f"GDACS={sum(1 for s in storms if s['source']=='GDACS')})")
    for s in sorted(storms, key=lambda s: s["basin"]):
        print(f"  {s['source']:5} {s['agency']:5} {s['basin']:18} {s['name'][:20]:20} "
              f"{s['category']:20} @ ({s['lat']:.1f},{s['lon']:.1f}) "
              f"wind={s.get('max_wind_kmh')}km/h")
