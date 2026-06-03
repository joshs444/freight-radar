"""Market-impact layer — the prices each chokepoint flag plausibly touches.

Honest, free, source-cited market CONTEXT (never causation): for each active
chokepoint flag we attach the dated levels of the instruments in its orbit
(Hormuz -> Brent/natgas, Suez/Red Sea -> Brent/bunker, Panama -> WTI ...).

Source chain per indicator, first that works, recording the REAL source + the
change basis on every value:
  1. FRED fredgraph.csv  — public-domain (cleanest); 1-2 business-day lag.
  2. Stooq single quote  — keyless; intraday OHLC (change vs open).
  3. Yahoo v8 chart      — keyless; day-over-day (vs previous close).

Container freight indices (FBX/WCI/SCFI/BDI) are NOT keyless free JSON
(login/licence/attribution walls) -> never scraped; left for a manual config.
Bunker VLSFO is MODELED from Brent (estimate:true), not quoted.

    python -m freight_radar.business.market    # -> frontend/public/data/market.json
"""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import httpx
import yaml

from ..config import BACKEND_DIR, publish_dir

LINKS_PATH = BACKEND_DIR / "config" / "market_links.yaml"
DISCLAIMER = "Dated market context, not causation — these prices move for many reasons."
STALE_DAYS = 6

INDICATORS = {
    "brent": {"name": "Brent crude", "unit": "$/bbl", "fred": "DCOILBRENTEU", "stooq": "cb.f", "yahoo": "BZ=F"},
    "wti": {"name": "WTI crude", "unit": "$/bbl", "fred": "DCOILWTICO", "stooq": "cl.f", "yahoo": "CL=F"},
    "natgas": {"name": "Henry Hub gas", "unit": "$/MMBtu", "fred": "DHHNGSP", "stooq": "ng.f", "yahoo": "NG=F"},
    "eurusd": {"name": "EUR/USD", "unit": "", "fred": "DEXUSEU", "stooq": "eurusd", "yahoo": "EURUSD=X"},
    "usdcny": {"name": "USD/CNY", "unit": "", "fred": "DEXCHUS", "stooq": "usdcny", "yahoo": "CNY=X"},
}
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _pct(cur: float, prev: float) -> float | None:
    return round((cur - prev) / prev * 100, 2) if prev else None


def _fred(client: httpx.Client, fid: str) -> dict | None:
    try:
        r = client.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={fid}",
                       headers={"User-Agent": BROWSER_UA}, timeout=15)
        r.raise_for_status()
        rows = [ln.split(",") for ln in r.text.splitlines() if "," in ln][1:]
        vals = [(d, float(v)) for d, v in rows if v not in (".", "")]
        if len(vals) < 2:
            return None
        (_, prev), (d, cur) = vals[-2], vals[-1]
        return {"value": round(cur, 4), "change_pct": _pct(cur, prev), "change_basis": "prev_close",
                "as_of": d, "source": "FRED (St. Louis Fed)", "source_url": f"https://fred.stlouisfed.org/series/{fid}"}
    except (httpx.HTTPError, ValueError):
        return None


def _stooq(client: httpx.Client, sym: str) -> dict | None:
    try:
        r = client.get(f"https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv", timeout=12)
        r.raise_for_status()
        lines = r.text.strip().splitlines()
        if len(lines) < 2:
            return None
        cols = lines[1].split(",")  # Symbol,Date,Time,Open,High,Low,Close,Volume
        d, op, close = cols[1], float(cols[3]), float(cols[6])
        return {"value": round(close, 4), "change_pct": _pct(close, op), "change_basis": "intraday",
                "as_of": d, "source": "Stooq", "source_url": f"https://stooq.com/q/?s={sym}"}
    except (httpx.HTTPError, ValueError, IndexError):
        return None


def _yahoo(client: httpx.Client, sym: str) -> dict | None:
    try:
        r = client.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d&range=5d",
                       headers={"User-Agent": BROWSER_UA}, timeout=12)
        r.raise_for_status()
        m = r.json()["chart"]["result"][0]["meta"]
        cur, prev = float(m["regularMarketPrice"]), float(m.get("chartPreviousClose") or 0)
        as_of = datetime.fromtimestamp(m.get("regularMarketTime", 0)).date().isoformat()
        return {"value": round(cur, 4), "change_pct": _pct(cur, prev), "change_basis": "prev_close",
                "as_of": as_of, "source": "Yahoo Finance", "source_url": f"https://finance.yahoo.com/quote/{sym}"}
    except (httpx.HTTPError, ValueError, KeyError):
        return None


def _stale(as_of: str, today: date) -> bool:
    try:
        return (today - date.fromisoformat(as_of[:10])).days > STALE_DAYS
    except ValueError:
        return False


def fetch_indicators(client: httpx.Client, today: date) -> dict:
    out: dict[str, dict] = {}
    for key, spec in INDICATORS.items():
        rec = _fred(client, spec["fred"]) or _stooq(client, spec["stooq"]) or _yahoo(client, spec["yahoo"])
        if rec:
            rec.update(name=spec["name"], unit=spec["unit"], stale=_stale(rec["as_of"], today))
        out[key] = rec or {"name": spec["name"], "unit": spec["unit"], "stale": True, "value": None}
    # bunker VLSFO: MODELED from Brent (not quoted)
    brent = out.get("brent") or {}
    if brent.get("value"):
        out["bunker_vlsfo"] = {
            "name": "VLSFO bunker (modeled)", "unit": "$/tonne",
            "value": round(brent["value"] * 7.5), "change_pct": brent.get("change_pct"),
            "change_basis": "modeled", "as_of": brent.get("as_of"),
            "source": "modeled from Brent (~7.5x)", "source_url": "https://shipandbunker.com/",
            "estimate": True, "basis": "modeled_from_brent", "stale": brent.get("stale", False),
        }
    return out


def run_market(flags: list[dict], today: date) -> dict:
    links = yaml.safe_load(LINKS_PATH.read_text()) or {}
    with httpx.Client(headers={"User-Agent": "freight-radar/0.1 (+portfolio)"}, follow_redirects=True) as client:
        indicators = fetch_indicators(client, today)
    items: dict[str, dict] = {}
    for f in flags:
        if f.get("lifecycle") == "resolved":
            continue
        linked = links.get(f["entity"], [])
        if linked:
            items[f["flag_id"]] = {"entity": f["entity"], "linked": linked,
                                   "relation": "exposure_context", "disclaimer": DISCLAIMER}
    return {"generated_at": datetime.now().isoformat(timespec="seconds"),
            "indicators": indicators, "items": items, "disclaimer": DISCLAIMER}


def run(ctx) -> dict:
    """Enricher entrypoint (EnrichCtx) -> writes market.json."""
    flags = json.loads(Path(ctx.flags_path).read_text())
    payload = run_market(flags, date.fromisoformat(ctx.today))
    (ctx.out_dir / "market.json").write_text(json.dumps(payload, indent=2))
    live = sum(1 for v in payload["indicators"].values() if v.get("value") is not None)
    return {"name": "market", "sidecar": "market.json", "indicators_live": live, "flags": len(payload["items"])}


if __name__ == "__main__":
    flags = json.loads((publish_dir() / "flags.json").read_text())
    p = run_market(flags, date.today())
    (publish_dir() / "market.json").write_text(json.dumps(p, indent=2))
    for k, v in p["indicators"].items():
        print(f"  {k:12} {v.get('value')} {v.get('unit','')}  {v.get('change_pct')}%  [{v.get('source','-')}]  as_of {v.get('as_of','-')}")
    print("flags linked:", list(p["items"].values())[:1])
