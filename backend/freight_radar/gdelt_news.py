"""Geo-tagged world-news layer (GDELT 2.0 GKG) -> news_geo.json for the globe dots.

The honest version of a "global news radar": each dot is ONE real, geo-located news
article from a recent GDELT window, categorised by what it is about (economy, energy,
trade/logistics, conflict, disaster) and clicking it opens the source article. It is
CONTEXT only — a possibly-related signal near a place, never a stated cause of any
freight number, and it carries no computed metric. (This is DISTINCT from news.json,
the per-flag business-headline enricher; this layer is a standalone map overlay.)

Why the raw 15-min export, not the DOC 2.0 query API: the query API 429s a shared CI
IP (see ADR-0004). The raw GKG master (data.gdeltproject.org/gdeltv2/lastupdate.txt)
is a tiny keyless download that never throttles in the weekly Action. We pull the most
recent few 15-min slices, keep only geo-located rows whose themes match a curated
business/disruption set, de-dupe by URL, and cap the set so the wire stays small.

Honesty: a weekly snapshot of a ~45-minute GDELT window, labelled with its exact
window timestamp — never implied to be live, never a headline we wrote, never tied to
a freight number. GKG carries no article title, so a dot shows its theme category +
place + outlet + date and links out to the real article. Source: The GDELT Project
(open data; underlying article copyrights remain with their publishers). Free, keyless.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import _http

log = logging.getLogger(__name__)

GDELT_BASE = "http://data.gdeltproject.org/gdeltv2"
LASTUPDATE = f"{GDELT_BASE}/lastupdate.txt"
N_SLICES = 3            # most recent 15-min GKG slices to pull (~45-min window)
CAP = 300              # max dots written to the sidecar (keeps the payload light)

# GKG 2.1 column indices (tab-separated, 27 cols) we read.
COL_DATE, COL_DOMAIN, COL_URL, COL_THEMES, COL_LOCS = 1, 3, 4, 7, 9

# Business/disruption theme buckets, in priority order (a row takes the FIRST bucket it
# matches). Match is a simple substring test against the V1Themes string (uppercased).
# A row matching NONE of these is dropped — this IS the "business-relevant" filter.
CATEGORY_RULES: list[tuple[str, str, tuple[str, ...]]] = [
    ("conflict", "Conflict & security",
     ("ARMEDCONFLICT", "MILITARY", "TERROR", "PROTEST", "FRAGILITY",
      "INSURGEN", "REBELLION", "WB_2433_CONFLICT", "WB_2470_PEACE", "SECURITY_SERVICES")),
    ("disaster", "Disaster & hazard",
     ("NATURAL_DISASTER", "MANMADE_DISASTER", "DISASTER", "ENV_", "WILDFIRE",
      "EARTHQUAKE", "FLOOD", "CRISISLEX_C03")),
    ("trade", "Trade & logistics",
     ("MARITIME", "PORT", "SHIPPING", "TRANSPORT", "CRISISLEX_C04_LOGISTICS",
      "WB_698_TRADE", "EXPORT", "IMPORT", "SUPPLY_CHAIN", "CUSTOMS", "TARIFF", "SANCTION")),
    ("energy", "Energy",
     ("ENERGY", "ENV_OIL", "PETROLEUM", "NATURAL_GAS", "ELECTRICITY",
      "WB_507_ENERGY", "FUEL", "POWER_")),
    ("economy", "Economy & markets",
     ("ECON_", "EPU_ECONOMY", "TAX_ECON", "STOCKMARKET", "INFLATION",
      "CENTRALBANK", "CURRENCY", "UNEMPLOYMENT", "BANKRUPTCY", "WB_TRADE")),
]

SOURCE = "GDELT Project 2.0 GKG — geo-tagged news coverage (detected; not headlines we wrote)"
SOURCE_URL = "https://www.gdeltproject.org/"
# Honest framing for the panel. Deliberately carries no causal language: a co-located,
# co-timed article the reader can weigh, never a stated cause of a freight number.
DISCLAIMER = ("Each dot is one geo-tagged article in a recent GDELT window — a "
              "possibly-related signal near a place, not a stated cause. Click to read "
              "the source.")


def _classify(themes: str) -> tuple[str, str] | None:
    # Match against GKG theme TOKENS, not the raw string, so a bare keyword can't match a
    # coincidental substring ("PORT" must not hit "SPORTS", "IMPORT" must not hit
    # "IMPORTANT"). Multi-segment / prefix keywords (those with "_") match as a substring
    # of a token; single-word keywords must be a whole underscore-delimited segment.
    tokens = [t.strip() for t in themes.upper().split(";") if t.strip()]
    segsets = [set(t.split("_")) for t in tokens]
    for key, label, kws in CATEGORY_RULES:
        for kw in kws:
            if "_" in kw:
                if any(kw in tok for tok in tokens):
                    return key, label
            elif any(kw in segs for segs in segsets):
                return key, label
    return None


def _first_geo(locs: str) -> tuple[float, float, str] | None:
    """First parseable (lat, lon, name) from a V1Locations field."""
    for loc in locs.split(";"):
        parts = loc.split("#")
        if len(parts) < 6:
            continue
        try:
            lat, lon = float(parts[4]), float(parts[5])
        except (ValueError, IndexError):
            continue
        if lat == 0.0 and lon == 0.0:
            continue  # GDELT uses 0,0 for "no real fix"
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            continue
        return lat, lon, parts[1].strip()
    return None


def _fmt_seen(raw_date: str) -> str:
    try:
        dt = datetime.strptime(raw_date.strip(), "%Y%m%d%H%M%S")
        return dt.strftime("%Y-%m-%d %H:%MZ")
    except ValueError:
        return ""


def _slice_urls(client) -> tuple[list[str], str]:
    """The N most recent GKG slice URLs + the window's latest timestamp (human)."""
    r = _http.get(client, LASTUPDATE)
    r.raise_for_status()
    latest = next((ln.split()[-1] for ln in r.text.splitlines()
                   if ln.strip().endswith("gkg.csv.zip")), None)
    if not latest:
        raise RuntimeError("no gkg slice in lastupdate.txt")
    ts = latest.rsplit("/", 1)[-1][:14]            # YYYYMMDDHHMMSS
    base = datetime.strptime(ts, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
    urls = [f"{GDELT_BASE}/{(base - timedelta(minutes=15 * i)).strftime('%Y%m%d%H%M%S')}"
            f".gkg.csv.zip" for i in range(N_SLICES)]
    window = base.strftime("%Y-%m-%d %H:%MZ")
    return urls, window


def _parse_slice(content: bytes) -> list[dict]:
    items: list[dict] = []
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        name = zf.namelist()[0]
        text = zf.read(name).decode("utf-8", errors="replace")
    for row in csv.reader(io.StringIO(text), delimiter="\t"):
        if len(row) <= COL_LOCS:
            continue
        cat = _classify(row[COL_THEMES])
        if not cat:
            continue
        geo = _first_geo(row[COL_LOCS])
        if not geo:
            continue
        url = row[COL_URL].strip()
        if not url.startswith("http"):
            continue
        lat, lon, place = geo
        items.append({
            "lat": round(lat, 3), "lon": round(lon, 3),
            "category": cat[0], "category_label": cat[1],
            "place": place, "domain": row[COL_DOMAIN].strip(),
            "url": url, "seen": _fmt_seen(row[COL_DATE]),
        })
    return items


def _collect() -> tuple[list[dict], str]:
    seen_urls: set[str] = set()
    items: list[dict] = []
    with _http.client(timeout=30.0) as c:
        urls, window = _slice_urls(c)
        for u in urls:
            try:
                resp = _http.get(c, u)
                if resp.status_code != 200 or len(resp.content) < 1000:
                    continue
                for it in _parse_slice(resp.content):
                    if it["url"] in seen_urls:
                        continue
                    seen_urls.add(it["url"])
                    items.append(it)
            except Exception as e:  # noqa: BLE001 — one bad slice never sinks the layer
                log.warning("gdelt slice %s skipped: %r", u, e)
    # newest first, then cap so the wire stays small
    items.sort(key=lambda x: x["seen"], reverse=True)
    return items[:CAP], window


def run(ctx) -> dict:
    out = Path(ctx.out_dir)
    try:
        items, window = _collect()
    except Exception as exc:  # noqa: BLE001 — degrade: the frontend hides an absent layer
        log.warning("news_geo layer unavailable this run: %r", exc)
        return {"name": "news_geo", "sidecar": "news_geo.json", "error": repr(exc)}
    if not items:
        return {"name": "news_geo", "sidecar": "news_geo.json",
                "error": "no geo-located coverage in window"}

    counts: dict[str, int] = {}
    for it in items:
        counts[it["category"]] = counts.get(it["category"], 0) + 1
    payload = {
        "generated_at": ctx.today,
        "as_of": getattr(ctx, "as_of", None) or ctx.today,
        "window": window,           # the GKG slice timestamp this snapshot was pulled at
        "source": SOURCE,
        "source_url": SOURCE_URL,
        "disclaimer": DISCLAIMER,
        "counts": counts,
        "items": items,
    }
    (out / "news_geo.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "news_geo", "sidecar": "news_geo.json",
            "count": len(items), "window": window, "by_category": counts}


if __name__ == "__main__":
    import types
    from datetime import date

    from ._log import configure as configure_logging
    from .config import publish_dir

    configure_logging()
    ctx = types.SimpleNamespace(out_dir=publish_dir(), as_of=date.today().isoformat(),
                                today=date.today().isoformat())
    print(run(ctx))
