"""Panama Canal Gatun Lake water-level + draft-projection enricher (ACP).

The Panama Canal is gravity-fed from Gatun Lake. When the lake drops (drought), the
Panama Canal Authority (ACP) cuts the maximum transit draft and adds surcharges —
weeks BEFORE PortWatch's transit count reflects it. PortWatch gives us only the
count (a lagging confirmation); the ACP publishes the lake level and projected draft
directly. This is a genuine leading indicator the trade-count data structurally
cannot provide.

Two free, keyless ACP CSVs:
  - Gatun lake level history (daily since 1965)
  - Gatun level + max-draft projection (next ~weeks)

We attach the current level (+ where it sits in the full history), a recent trend,
and the projected max Neopanamax/Panamax draft + surcharge to the Panama chokepoint.
Drafts are ACP estimates (their own disclaimer) — labelled and cited as such.
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path

import duckdb
import httpx

HISTORY_URL = "https://evtms-rpts.pancanal.com/eng/h2o/Download_Gatun_Lake_Water_Level_History.csv"
PROJECTION_URL = "https://evtms-rpts.pancanal.com/eng/h2o/Gatun_Water_Level_Projection.csv"
PANAMA_PORTID = "chokepoint2"
NORMAL_MAX_DRAFT_FT = 50.0  # Neopanamax design max; ACP restricts below this in drought
SPARK_DAYS = 120
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _get(url: str, client: httpx.Client) -> str:
    r = client.get(url)
    r.raise_for_status()
    return r.text


def _parse_history(text: str) -> list[tuple[str, float]]:
    out = []
    for row in csv.reader(io.StringIO(text)):
        if len(row) < 2 or not row[0] or row[0].upper().startswith("DATE"):
            continue
        try:
            out.append((row[0].strip(), float(row[1])))
        except ValueError:
            continue
    return out


def _parse_projection(text: str) -> list[dict]:
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if ln.lower().startswith("projected_date")), None)
    if start is None:
        return []
    out = []
    for row in csv.reader(lines[start + 1:]):
        if len(row) < 5 or not row[0].strip():
            continue
        try:
            out.append({
                "date": row[0].strip(),
                "level_ft": float(row[1]),
                "surcharge_pct": float(row[2]),
                "neopanamax_draft_ft": float(row[3]),
                "panamax_draft_ft": float(row[4]),
            })
        except ValueError:
            continue
    return out


def _pctile_of(value: float, values: list[float]) -> float:
    if not values:
        return 0.0
    below = sum(1 for v in values if v <= value)
    return round(below / len(values) * 100, 1)


def build(client: httpx.Client | None = None) -> dict:
    own = client is None
    client = client or httpx.Client(timeout=25.0, headers={"User-Agent": BROWSER_UA})
    try:
        hist = _parse_history(_get(HISTORY_URL, client))
        proj = _parse_projection(_get(PROJECTION_URL, client))
    finally:
        if own:
            client.close()
    if not hist:
        return {"available": False}

    levels = [v for _, v in hist]
    current = levels[-1]
    as_of = hist[-1][0]
    change_30d = round(current - levels[-31], 2) if len(levels) >= 31 else None
    change_365d = round(current - levels[-366], 2) if len(levels) >= 366 else None

    drafts = [p["neopanamax_draft_ft"] for p in proj] or [NORMAL_MAX_DRAFT_FT]
    min_neo = min(drafts)
    restricted = min_neo < NORMAL_MAX_DRAFT_FT
    surcharge_now = proj[0]["surcharge_pct"] if proj else 0.0

    return {
        "available": True,
        "portid": PANAMA_PORTID,
        "name": "Panama Canal",
        "as_of": as_of,
        "current_level_ft": round(current, 2),
        "pctile_alltime": _pctile_of(current, levels),  # 0 = lowest ever, 100 = highest
        "change_30d_ft": change_30d,
        "change_365d_ft": change_365d,
        "level_spark": [round(v, 2) for v in levels[-SPARK_DAYS:]],
        "normal_max_draft_ft": NORMAL_MAX_DRAFT_FT,
        "min_projected_neopanamax_draft_ft": round(min_neo, 1),
        "draft_restricted": restricted,
        "surcharge_pct_now": surcharge_now,
        "projection": proj[:12],
        "source": "Panama Canal Authority (ACP)",
        "source_url": "https://pancanal.com/en/maritime-services/water-level/",
        "disclaimer": "Projected drafts are ACP estimates for reference only; official drafts come via Advisories to Shipping.",
    }


def run(ctx) -> dict:
    out = Path(ctx.out_dir)
    try:
        payload = build()
    except Exception as e:  # noqa: BLE001 — degrade like every other enricher
        payload = {"available": False, "error": repr(e)}
    # stamp lat/lon from the dim if present (so the card can fly the globe)
    if payload.get("available"):
        try:
            con = duckdb.connect(str(ctx.db_path), read_only=True)
            row = con.execute("SELECT lat, lon FROM dim_chokepoint WHERE portid=?",
                              [PANAMA_PORTID]).fetchone()
            con.close()
            if row:
                payload["lat"], payload["lon"] = float(row[0]), float(row[1])
        except Exception:  # noqa: BLE001
            pass
    payload["generated_at"] = ctx.today
    (out / "gatun.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "gatun", "sidecar": "gatun.json",
            "level": payload.get("current_level_ft"), "restricted": payload.get("draft_restricted")}


if __name__ == "__main__":
    p = build()
    print(json.dumps({k: v for k, v in p.items() if k not in ("level_spark", "projection")}, indent=2))
    print("projection[0:3]:", json.dumps(p.get("projection", [])[:3]))
