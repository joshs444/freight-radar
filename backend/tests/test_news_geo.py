"""The GDELT world-news layer's honesty contract — the machine-enforced anti-centrum guard.

This layer is the riskiest for the brand (news invites implied causation), so its
discipline is enforced by tests, not reviewer vigilance:
  1. it is a CONTEXT layer — registered on the enricher registry, sidecar-only, and it
     never reads the DB or writes flags.json, so a news signal can NEVER mutate a
     computed freight number;
  2. no causal/forecast verb appears in its copy (backend module OR the frontend news
     layer lines) — where centrum-ai asserts a predicted cascade, we state the cited
     signal and stop.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import freight_radar.publish as publish
from freight_radar import gdelt_news as g
from freight_radar.enrich import ENRICHERS
from freight_radar.honesty.lexicon import CAUSAL_FORECAST as CAUSAL  # one shared banned list

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend" / "src"


def test_news_geo_is_registered_context_sidecar_only():
    entry = next((e for e in ENRICHERS if e[0] == "news_geo"), None)
    assert entry is not None, "news_geo must be on the enricher registry"
    assert entry[2] is False, "news_geo is independent of flags (depends_on_flags=False)"
    assert "news_geo" in publish._SIDECARS, "news_geo must be a reported sidecar"


def test_news_geo_never_touches_the_fact_path():
    """Structural guarantee: the module can't read the DB or rewrite flags -> it cannot
    move any computed number. (Context joins enrich.py, never the WAP fact tables.)"""
    src = (REPO / "backend" / "freight_radar" / "gdelt_news.py").read_text()
    for forbidden in ("duckdb", "fct_", "flags_path", "flags.json"):
        assert forbidden not in src, f"news_geo must not touch {forbidden}"


def test_news_geo_backend_copy_has_no_causal_verbs():
    src = (REPO / "backend" / "freight_radar" / "gdelt_news.py").read_text().lower()
    hits = [v for v in CAUSAL if v in src]
    assert not hits, f"causal/forecast verb in news_geo backend copy: {hits}"


def test_news_geo_frontend_copy_has_no_causal_verbs():
    """Scan every frontend line that mentions the news layer for a causal/forecast verb
    (the wind FORECAST copy is legitimately allowed and is not a news line)."""
    offenders: list[str] = []
    for f in ("Globe.tsx", "components/LayerPanel.tsx"):
        for ln in (FRONTEND / f).read_text().splitlines():
            low = ln.lower()
            if "news" in low or "gdelt" in low or "geo-tagged" in low:
                offenders += [f"{f}: {ln.strip()}" for v in CAUSAL if v in low]
    assert not offenders, f"causal/forecast verb in news layer copy: {offenders}"


def _fake_gkg_zip(rows: list[list[str]]) -> bytes:
    text = "\n".join("\t".join(r) for r in rows)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("slice.gkg.csv", text)
    return buf.getvalue()


def _row(date="20260606160000", domain="reuters.com", url="https://reuters.com/x",
         themes="", locs=""):
    r = [""] * 27
    r[g.COL_DATE], r[g.COL_DOMAIN], r[g.COL_URL] = date, domain, url
    r[g.COL_THEMES], r[g.COL_LOCS] = themes, locs
    return r


def test_parse_keeps_business_geo_rows_and_drops_the_rest():
    rows = [
        _row(themes="ECON_STOCKMARKET;MARITIME", locs="4#Shanghai, China#CH#CH23#31.2#121.5#-1"),
        _row(url="https://x.com/celeb", themes="TAX_FNCACT;ENTERTAINMENT",
             locs="4#Hollywood#US#USCA#34.0#-118.2#-2"),                 # not business -> drop
        _row(url="https://y.com/econ", themes="ECON_INFLATION", locs=""),  # no geo -> drop
    ]
    items = g._parse_slice(_fake_gkg_zip(rows))
    assert len(items) == 1
    it = items[0]
    assert it["category"] == "trade" and it["place"] == "Shanghai, China"
    assert (it["lat"], it["lon"]) == (31.2, 121.5)
    assert it["url"] == "https://reuters.com/x"


def test_classify_priority_and_geo_zero_island_rejected():
    assert g._classify("ARMEDCONFLICT;ECON_STOCKMARKET")[0] == "conflict"  # priority order
    assert g._classify("TAX_FNCACT;SPORTS") is None
    assert g._first_geo("1#Nowhere#XX#XX#0#0#0") is None  # 0,0 is GDELT's "no fix"
    assert g._first_geo("4#Cairo#EG#EG#30.05#31.25#9") == (30.05, 31.25, "Cairo")
