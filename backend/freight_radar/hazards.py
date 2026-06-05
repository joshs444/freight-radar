"""Natural-hazard / official-event layer (IMF PortWatch disruptions DB = GDACS).

The IMF PortWatch "disruptions database" is a curated feed of GDACS official
natural-hazard events — tropical cyclones, floods, earthquakes, volcanoes — and,
crucially, each event lists the exact PortWatch port IDs it affected. We fetch the
recent events, match them to monitored infrastructure (affected ports by ID +
chokepoints by spatial proximity), and write disruptions.json. Any flag whose
port/chokepoint sits inside a contemporaneous event gets an `official_event`
corroboration — the honest "is something official backing this up?" cross-check.

It's scrupulous about dates: events are stamped with their own from/to and labelled
"most recent", never implied to be live. Today's flags (geopolitical Hormuz,
congestion at Shanghai) have no natural-hazard overlap, and the UI says so; when a
storm does strike a flagged port, the corroboration appears automatically.

Source: IMF PortWatch (https://portwatch.imf.org/) — same ArcGIS host as the trade
data; free, keyless. GDACS alert levels: GREEN / ORANGE / RED.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import duckdb
import httpx

from . import _http
from .config import ARCGIS_HOST

DISRUPTIONS_URL = f"{ARCGIS_HOST}/portwatch_disruptions_database/FeatureServer/0/query"
WINDOW_DAYS = 240          # how far back to surface "recent" hazard events
CORROBORATE_DAYS = 30      # a flag is corroborated only by a near-contemporaneous event
CHOKEPOINT_RADIUS_KM = 350  # spatial match of an event to a chokepoint

EVENT_TYPES = {
    "TC": "Tropical cyclone", "FL": "Flood", "EQ": "Earthquake", "VO": "Volcano",
    "DR": "Drought", "TS": "Tsunami", "WF": "Wildfire",
}
ALERT_RANK = {"RED": 3, "ORANGE": 2, "GREEN": 1}


def _epoch_to_date(ms) -> str | None:
    if ms in (None, ""):
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()
    except (ValueError, OSError, TypeError):
        return None


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def fetch_events(as_of: date, client: httpx.Client | None = None) -> list[dict]:
    """Fetch recent GDACS events from the IMF disruptions DB (raw attributes)."""
    params = {
        "where": f"year>={as_of.year - 1}",
        "outFields": ("eventid,eventtype,eventname,htmlname,alertlevel,country,"
                      "fromdate,todate,lat,long,n_affectedports,affectedports,affectedpopulation,severitytext"),
        "orderByFields": "todate DESC",
        "resultRecordCount": 200,
        "f": "json",
    }
    own = client is None
    client = client or _http.client(timeout=20.0)
    try:
        r = _http.get(client, DISRUPTIONS_URL, params=params)
        r.raise_for_status()
        feats = r.json().get("features", [])
    finally:
        if own:
            client.close()
    return [f.get("attributes", {}) for f in feats]


def _parse_affected(raw) -> list[str]:
    if not raw:
        return []
    return [p.strip() for p in str(raw).replace(",", ";").split(";") if p.strip().startswith("port")]


def _load_infra(con: duckdb.DuckDBPyConnection) -> tuple[dict, list[dict]]:
    ports = {pid: name for pid, name in con.execute(
        "SELECT portid, portname FROM dim_port").fetchall()}
    chokes = [{"portid": pid, "name": name, "lat": lat, "lon": lon}
              for pid, name, lat, lon in con.execute(
                  "SELECT portid, fullname, lat, lon FROM dim_chokepoint").fetchall()]
    return ports, chokes


def build_events(raw_events: list[dict], ports: dict, chokes: list[dict], as_of: date) -> list[dict]:
    cutoff = as_of - timedelta(days=WINDOW_DAYS)
    out = []
    for a in raw_events:
        to_d = _epoch_to_date(a.get("todate"))
        from_d = _epoch_to_date(a.get("fromdate"))
        if not to_d:
            continue
        try:
            to_date = date.fromisoformat(to_d)
        except ValueError:
            continue
        if to_date < cutoff:        # too old to be "recent"
            continue
        affected = [{"portid": pid, "name": ports[pid]} for pid in _parse_affected(a.get("affectedports"))
                    if pid in ports]
        lat, lon = a.get("lat"), a.get("long")
        near_ch = []
        if lat is not None and lon is not None:
            for c in chokes:
                if c["lat"] is None or c["lon"] is None:
                    continue
                km = _haversine_km(lat, lon, c["lat"], c["lon"])
                if km <= CHOKEPOINT_RADIUS_KM:
                    near_ch.append({"portid": c["portid"], "name": c["name"], "km": round(km)})
        if not affected and not near_ch:
            continue                # only surface events that touch monitored infra
        etype = a.get("eventtype")
        out.append({
            "eventid": a.get("eventid"),
            "type": etype,
            "type_label": EVENT_TYPES.get(etype, etype),
            "name": a.get("htmlname") or a.get("eventname"),
            "alertlevel": a.get("alertlevel"),
            "country": a.get("country"),
            "from": from_d, "to": to_d,
            "lat": lat, "lon": lon,
            "severity": a.get("severitytext"),  # GDACS human-readable magnitude
            "affected_ports": affected[:8],
            "n_affected_ports": len(affected),
            "near_chokepoints": sorted(near_ch, key=lambda x: x["km"]),
            "affected_population": a.get("affectedpopulation"),
        })
    out.sort(key=lambda e: (ALERT_RANK.get(e["alertlevel"], 0), e["to"]), reverse=True)
    return out


def corroborate(flags: list[dict], events: list[dict]) -> int:
    """Attach `official_event` to flags whose infra sits in a contemporaneous event."""
    n = 0
    for f in flags:
        if f.get("lifecycle") == "resolved":
            continue
        pid = f.get("portid")
        try:
            f_date = date.fromisoformat(f.get("as_of", ""))
        except (ValueError, TypeError):
            f_date = None
        best = None
        for e in events:
            in_ports = any(p["portid"] == pid for p in e["affected_ports"])
            in_chokes = any(c["portid"] == pid for c in e["near_chokepoints"])
            if not (in_ports or in_chokes):
                continue
            if f_date:
                try:
                    e_to = date.fromisoformat(e["to"])
                    e_from = date.fromisoformat(e["from"]) if e.get("from") else e_to
                except (ValueError, TypeError):
                    continue
                if not (e_from - timedelta(days=CORROBORATE_DAYS) <= f_date <= e_to + timedelta(days=CORROBORATE_DAYS)):
                    continue
            best = e
            break
        if best:
            f["official_event"] = {
                "name": best["name"], "type_label": best["type_label"],
                "alertlevel": best["alertlevel"], "from": best["from"], "to": best["to"],
                "source": "IMF PortWatch / GDACS",
            }
            n += 1
        else:
            f.pop("official_event", None)
    return n


def run(ctx) -> dict:
    out = Path(ctx.out_dir)
    as_of = date.fromisoformat(ctx.as_of) if ctx.as_of else date.today()
    raw = fetch_events(as_of)
    con = duckdb.connect(str(ctx.db_path), read_only=True)
    try:
        ports, chokes = _load_infra(con)
    finally:
        con.close()
    events = build_events(raw, ports, chokes, as_of)

    # corroborate flags (write back into flags.json, like news/exposure do)
    corroborated = 0
    flags_path = Path(ctx.flags_path)
    if flags_path.exists():
        flags = json.loads(flags_path.read_text())
        corroborated = corroborate(flags, events)
        flags_path.write_text(json.dumps(flags, indent=2))

    red = sum(1 for e in events if e["alertlevel"] == "RED")
    payload = {
        "generated_at": ctx.today,
        "as_of": as_of.isoformat(),
        "window_days": WINDOW_DAYS,
        "source": "IMF PortWatch disruptions database (GDACS official hazard alerts)",
        "source_url": "https://portwatch.imf.org/",
        "events": events,
        "counts": {"events": len(events), "red": red,
                   "flags_corroborated": corroborated},
    }
    (out / "disruptions.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "disruptions", "sidecar": "disruptions.json",
            "events": len(events), "corroborated": corroborated}


if __name__ == "__main__":
    from .config import db_path
    as_of = date(2026, 5, 31)
    raw = fetch_events(as_of)
    con = duckdb.connect(str(db_path()), read_only=True)
    ports, chokes = _load_infra(con)
    con.close()
    evs = build_events(raw, ports, chokes, as_of)
    print(f"raw={len(raw)} → infra-touching recent={len(evs)}")
    for e in evs[:12]:
        ap = ", ".join(p["name"] for p in e["affected_ports"][:3])
        nc = ", ".join(c["name"] for c in e["near_chokepoints"][:2])
        print(f"  {e['alertlevel']:6} {e['type_label']:16} {e['name'][:34]:34} {e['from']}→{e['to']} "
              f"ports[{e['n_affected_ports']}]:{ap[:40]} choke:{nc}")
