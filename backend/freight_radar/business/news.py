"""Honest per-area news enrichment — the 'who else is reporting it' layer.

For each active flag we fetch REAL, dated, cited articles for that entity from free
Google News RSS (zero marginal cost, no API key), gate hard (resolvable URL +
parseable date + maritime context), and attach them as **possibly related** — never
as a confirmed cause of a statistical anomaly. Citations are owned by this
deterministic fetcher; no LLM writes or invents a headline, date, or URL.

    python -m freight_radar.business.news        # -> frontend/public/data/news.json

Honesty invariants (also asserted in tests):
  * every attached item has a non-null url AND a parseable published date
  * relation == "possibly_related" and a disclaimer are always present
  * a flag with no qualifying coverage shows an honest empty state
"""

from __future__ import annotations

import json
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import date, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import httpx

from ..config import publish_dir

DISCLAIMER = "Headlines co-occurring in time and place — not a confirmed cause of this anomaly."
CONTEXT = "(shipping OR port OR vessel OR cargo OR trade OR strait OR canal)"


def _gnews_url(entity: str, days: int) -> str:
    q = f'"{entity}" {CONTEXT} when:{days}d'
    return (
        "https://news.google.com/rss/search?q="
        + urllib.parse.quote(q)
        + "&hl=en-US&gl=US&ceid=US:en"
    )


def fetch_for_entity(client: httpx.Client, entity: str, as_of: str, today: date, max_items: int = 4) -> list[dict]:
    try:
        days = max(30, min(120, (today - date.fromisoformat(as_of)).days + 21))
    except ValueError:
        days = 60
    try:
        r = client.get(_gnews_url(entity, days), timeout=20)
        r.raise_for_status()
        root = ET.fromstring(r.text)
    except (httpx.HTTPError, ET.ParseError):
        return []

    items: list[dict] = []
    for it in root.iter("item"):
        link = (it.findtext("link") or "").strip()
        pub = it.findtext("pubDate")
        if not link or not pub:
            continue
        try:
            published = parsedate_to_datetime(pub).date().isoformat()
        except (TypeError, ValueError):
            continue  # gate: no parseable date -> drop
        title = (it.findtext("title") or "").strip()
        src_el = it.find("source")
        source = (src_el.text if src_el is not None else "") or ""
        if not source and " - " in title:
            title, source = title.rsplit(" - ", 1)
        items.append({"title": title.strip(), "url": link, "source": source.strip(), "published": published})

    seen, out = set(), []
    for x in sorted(items, key=lambda z: z["published"], reverse=True):
        key = x["title"][:60].lower()
        if not x["title"] or key in seen:
            continue
        seen.add(key)
        out.append(x)
        if len(out) >= max_items:
            break
    return out


def enrich_news(flags: list[dict], today: date) -> dict:
    """Fetch coverage for each active flag; return the news.json payload."""
    active = [f for f in flags if f.get("lifecycle") != "resolved"]
    items: dict[str, dict] = {}
    with httpx.Client(headers={"User-Agent": "freight-radar/0.1 (+portfolio)"}, follow_redirects=True) as client:
        for f in active:
            arts = fetch_for_entity(client, f["entity"], f["as_of"], today)
            items[f["flag_id"]] = {
                "entity": f["entity"],
                "items": arts,
                "relation": "possibly_related",
                "disclaimer": DISCLAIMER,
                "outlet_count": len({a["source"].lower() for a in arts if a["source"]}),
            }
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "search_date": today.isoformat(),
        "items": items,
    }


def enrich_news_from_files(flags_path: Path = None, out_dir: Path = None, today: date | None = None) -> dict:
    out = out_dir or publish_dir()
    flags_path = flags_path or (out / "flags.json")
    today = today or date.today()
    flags = json.loads(Path(flags_path).read_text())
    payload = enrich_news(flags, today)
    (out / "news.json").write_text(json.dumps(payload, indent=2))
    return payload


if __name__ == "__main__":
    p = enrich_news_from_files()
    for fid, blk in p["items"].items():
        print(f"{blk['entity']:22} {len(blk['items'])} items ({blk['outlet_count']} outlets)")
        for a in blk["items"][:2]:
            print(f"    [{a['published']}] {a['title'][:70]}  — {a['source']}")
