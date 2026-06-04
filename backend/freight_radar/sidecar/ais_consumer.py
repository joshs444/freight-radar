"""AIS garnish — OPTIONAL, non-load-bearing, deliberately isolated.

A SEPARATE asyncio process (never a Temporal activity, never read by the flag
engine). It writes ``ships.json`` for the deck.gl TripsLayer and degrades safely:

    live    : AISSTREAM_API_KEY set -> real moving-ship trails in hotspot bboxes
    demo    : no key -> clearly-labelled SIMULATED tracks so the trails are demoable
    offline : socket failed / killed -> empty ships, the map + every number unaffected

    python -m freight_radar.sidecar.ais_consumer            # live if key, else demo
    python -m freight_radar.sidecar.ais_consumer --demo     # force simulated
    python -m freight_radar.sidecar.ais_consumer --offline  # force empty

The honesty rule holds: demo mode stamps mode="demo" + a note, and the UI labels
it "SIMULATED" — it is never presented as real vessel data.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import random
from datetime import datetime
from pathlib import Path

from ..config import publish_dir

# (name, center_lon, center_lat, heading_deg) — real maritime hotspots
HOTSPOTS = [
    ("Suez approaches", 32.55, 29.9, 20),
    ("Singapore Strait", 103.8, 1.2, 95),
    ("Yangtze / Shanghai", 122.0, 31.2, 60),
    ("Gibraltar", -5.5, 35.95, 80),
]
SHIP_TYPES = ["container", "tanker", "dry_bulk", "general_cargo"]
T_MAX = 100  # TripsLayer loops currentTime over 0..T_MAX


def _ships_path(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir / "ships.json"


def write_offline(out_dir: Path = None) -> dict:
    out = _ships_path(out_dir or publish_dir())
    payload = {"mode": "offline", "generated_at": datetime.now().isoformat(timespec="seconds"),
               "t_max": T_MAX, "ships": []}
    out.write_text(json.dumps(payload, separators=(",", ":")))
    return payload


def generate_demo(out_dir: Path = None, per_hotspot: int = 14) -> dict:
    """Deterministic SIMULATED tracks near real hotspots (clearly labelled)."""
    rng = random.Random(42)
    ships = []
    for hi, (name, clon, clat, heading) in enumerate(HOTSPOTS):
        for k in range(per_hotspot):
            # random-but-seeded start offset + slightly varied heading
            olon = clon + rng.uniform(-1.6, 1.6)
            olat = clat + rng.uniform(-1.1, 1.1)
            hd = math.radians(heading + rng.uniform(-35, 35))
            speed = rng.uniform(0.018, 0.05)  # deg per step
            curve = rng.uniform(-0.0011, 0.0011)
            path = []
            lon, lat, ang = olon, olat, hd
            for step in range(9):
                t = int(step / 8 * T_MAX)
                path.append([round(lon, 4), round(lat, 4), t])
                ang += curve
                lon += math.cos(ang) * speed * 8
                lat += math.sin(ang) * speed * 8
            ships.append({
                "mmsi": f"D{hi}{k:02d}",
                "name": f"SIM {name.split()[0].upper()} {k+1}",
                "type": SHIP_TYPES[(hi + k) % len(SHIP_TYPES)],
                "path": path,
            })
    payload = {
        "mode": "demo",
        "note": "Simulated demo tracks — NOT live vessel data.",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "t_max": T_MAX,
        "ships": ships,
    }
    _ships_path(out_dir or publish_dir()).write_text(json.dumps(payload, separators=(",", ":")))
    return payload


async def run_live(out_dir: Path = None, key: str = "", write_every: float = 4.0) -> None:
    """Best-effort live AIS. Subscribes to hotspot bboxes, accumulates bounded
    per-MMSI trails, periodically writes ships.json. Any failure -> offline."""
    import websockets  # local import: only needed on the live path

    out = out_dir or publish_dir()
    bboxes = [[[clat - 1.5, clon - 1.5], [clat + 1.5, clon + 1.5]] for _, clon, clat, _ in HOTSPOTS]
    trails: dict[str, list] = {}
    try:
        async with websockets.connect("wss://stream.aisstream.io/v0/stream") as ws:
            await ws.send(json.dumps({
                "APIKey": key,
                "BoundingBoxes": bboxes,
                "FilterMessageTypes": ["PositionReport"],
            }))
            last_write = 0.0
            loop = asyncio.get_event_loop()
            async for raw in ws:
                msg = json.loads(raw)
                pr = msg.get("Message", {}).get("PositionReport")
                meta = msg.get("MetaData", {})
                if pr:
                    mmsi = str(meta.get("MMSI"))
                    pt = [pr.get("Longitude"), pr.get("Latitude")]
                    tr = trails.setdefault(mmsi, [])
                    tr.append(pt)
                    del tr[:-12]  # keep last 12 points
                now = loop.time()
                if now - last_write >= write_every:
                    last_write = now
                    _write_live(out, trails)
    except Exception as exc:  # noqa: BLE001 - garnish: any failure degrades to offline
        write_offline(out)
        print(f"AIS live failed ({exc!r}); wrote offline badge")


AIS_URL = "wss://stream.aisstream.io/v0/stream"


def _ais_type(code) -> str:
    """AIS ship-type code -> coarse class (AIS only resolves cargo vs tanker, etc.)."""
    try:
        c = int(code)
    except (TypeError, ValueError):
        return "vessel"
    if 70 <= c <= 79:
        return "cargo"
    if 80 <= c <= 89:
        return "tanker"
    if 60 <= c <= 69:
        return "passenger"
    if 30 <= c <= 39:
        return "fishing"
    return "vessel"


def _chokepoint_bboxes(half: float = 0.7) -> list:
    """[[SW_lat,SW_lon],[NE_lat,NE_lon]] boxes around the 28 monitored chokepoints
    (read from the DB). Falls back to the curated HOTSPOTS when no DB is present."""
    try:
        import duckdb

        from ..config import db_path

        con = duckdb.connect(str(db_path()), read_only=True)
        rows = con.execute(
            "SELECT lat, lon FROM dim_chokepoint WHERE lat IS NOT NULL AND lon IS NOT NULL"
        ).fetchall()
        con.close()
        if rows:
            return [[[lat - half, lon - half], [lat + half, lon + half]] for lat, lon in rows]
    except Exception:  # noqa: BLE001 - fall back to hotspots if the DB isn't there
        pass
    return [[[clat - 1.5, clon - 1.5], [clat + 1.5, clon + 1.5]] for _, clon, clat, _ in HOTSPOTS]


async def snapshot_live(out_dir: Path = None, key: str = "", duration_s: float = 70.0) -> dict:
    """One-shot REAL AIS: collect a ~duration_s window of position reports near the
    monitored chokepoints, keep the LATEST position per vessel, write ships.json as
    current positions (not trails). Any failure degrades to offline. Honest: this is a
    live sample near the chokepoints, never 'all ships'."""
    import websockets

    out = out_dir or publish_dir()
    bboxes = _chokepoint_bboxes()
    latest: dict[str, dict] = {}
    static: dict[str, dict] = {}

    async def _collect() -> None:
        async with websockets.connect(AIS_URL, ping_interval=20, max_size=2 ** 22) as ws:
            await ws.send(json.dumps({
                "APIKey": key,
                "BoundingBoxes": bboxes,
                "FilterMessageTypes": ["PositionReport", "ShipStaticData"],
            }))
            async for raw in ws:
                msg = json.loads(raw)
                if msg.get("error") or msg.get("Error"):
                    raise RuntimeError(f"aisstream error: {msg.get('error') or msg.get('Error')}")
                mtype = msg.get("MessageType")
                meta = msg.get("MetaData", {})
                mmsi = str(meta.get("MMSI") or "")
                if not mmsi:
                    continue
                if mtype == "PositionReport":
                    pr = msg.get("Message", {}).get("PositionReport", {})
                    lat, lon = pr.get("Latitude"), pr.get("Longitude")
                    if lat is None or lon is None:
                        continue
                    hdg = pr.get("TrueHeading")
                    if hdg is None or hdg >= 511:
                        hdg = pr.get("Cog") or 0
                    latest[mmsi] = {"lon": round(lon, 4), "lat": round(lat, 4), "heading": round(hdg) % 360}
                elif mtype == "ShipStaticData":
                    sd = msg.get("Message", {}).get("ShipStaticData", {})
                    static[mmsi] = {"name": str(sd.get("Name") or "").strip(), "type": _ais_type(sd.get("Type"))}

    try:
        await asyncio.wait_for(_collect(), timeout=duration_s)
    except asyncio.TimeoutError:
        pass  # expected — we deliberately cap the collection window
    except Exception as exc:  # noqa: BLE001 - garnish: any failure degrades to offline
        write_offline(out)
        print(f"AIS snapshot failed ({exc!r}); wrote offline badge")
        return {"mode": "offline", "count": 0}

    vessels = [
        {"mmsi": mmsi, "lon": p["lon"], "lat": p["lat"], "heading": p["heading"],
         "type": static.get(mmsi, {}).get("type", "vessel"),
         "name": static.get(mmsi, {}).get("name", "")}
        for mmsi, p in latest.items()
    ]
    payload = {
        "mode": "live",
        "note": "Real AIS vessel positions near the monitored chokepoints, sampled at publish (a point-in-time sample, not all ships).",
        "source": "aisstream.io",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "count": len(vessels),
        "vessels": vessels,
    }
    _ships_path(out).write_text(json.dumps(payload, separators=(",", ":")))
    return {"mode": "live", "count": len(vessels)}


def _write_live(out: Path, trails: dict[str, list]) -> None:
    ships = []
    for mmsi, pts in trails.items():
        if len(pts) < 2:
            continue
        path = [[round(p[0], 4), round(p[1], 4), int(i / (len(pts) - 1) * T_MAX)]
                for i, p in enumerate(pts)]
        ships.append({"mmsi": mmsi, "name": mmsi, "type": "unknown", "path": path})
    payload = {"mode": "live", "generated_at": datetime.now().isoformat(timespec="seconds"),
               "t_max": T_MAX, "ships": ships}
    _ships_path(out).write_text(json.dumps(payload, separators=(",", ":")))


def main() -> None:
    ap = argparse.ArgumentParser(description="Freight Radar AIS garnish (optional)")
    ap.add_argument("--demo", action="store_true", help="force simulated tracks")
    ap.add_argument("--offline", action="store_true", help="force empty/offline")
    ap.add_argument("--snapshot", action="store_true",
                    help="one-shot REAL position snapshot near the chokepoints (needs key)")
    args = ap.parse_args()
    key = os.environ.get("AISSTREAM_API_KEY", "")

    if args.offline:
        print("ships.json: offline", write_offline()["mode"])
    elif args.snapshot:
        if not key:
            print("ships.json: no AISSTREAM_API_KEY -> demo"); generate_demo()
        else:
            r = asyncio.run(snapshot_live(key=key))
            print(f"ships.json: {r['mode']} ({r.get('count', 0)} live vessel positions)")
    elif args.demo or not key:
        n = len(generate_demo()["ships"])
        print(f"ships.json: demo ({n} simulated ships)" + ("" if not args.demo else " [forced]"))
        if not key and not args.demo:
            print("  (no AISSTREAM_API_KEY -> simulated; set the key for live trails)")
    else:
        asyncio.run(run_live(key=key))


if __name__ == "__main__":
    main()
