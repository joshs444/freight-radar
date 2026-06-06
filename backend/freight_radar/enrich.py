"""Generic enricher registry — the single seam every signal layer rides.

A code review found the optional enrichers (timeseries/news/...) were ORPHANED:
only ``publish.py`` hard-called ``exposure`` inline, and the Temporal loop called
none of them, so timeseries.json / news.json went stale on every scheduled tick.

This registry fixes that once: ``publish_static`` AND the Temporal loop both call
``run_enrichers(ctx)``, which runs each registered enricher, writes its one sidecar,
and SWALLOWS per-enricher failures (the server-side mirror of the frontend's
``.catch(()=>null)``) — one bad layer never aborts publish. New layers (market,
weather, dwell, internal) register as a one-liner here.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

import duckdb

from .config import db_path, publish_dir

log = logging.getLogger(__name__)


@dataclass
class EnrichCtx:
    db_path: Path
    out_dir: Path
    flags_path: Path   # data/flags.json
    as_of: str         # snapshot max date 'YYYY-MM-DD'
    today: str         # 'YYYY-MM-DD'


# --- adapters: wrap each existing enricher to the (ctx)->receipt interface ---
def _exposure(ctx: EnrichCtx) -> dict:
    from .business.exposure import enrich_from_files
    s = enrich_from_files(flags_path=ctx.flags_path, out_dir=ctx.out_dir, db=ctx.db_path)
    return {"name": "exposure", "sidecar": "exposure.json",
            "exposed_value_usd": s.get("exposed_value_usd"),
            "coverage_pct": s.get("coverage_pct"),
            "disruptions": s.get("active_disruptions_hitting_you")}


def _news(ctx: EnrichCtx) -> dict:
    from .business.news import enrich_news_from_files
    p = enrich_news_from_files(flags_path=ctx.flags_path, out_dir=ctx.out_dir,
                               today=date.fromisoformat(ctx.today))
    return {"name": "news", "sidecar": "news.json", "flags": len(p.get("items", {}))}


def _news_geo(ctx: EnrichCtx) -> dict:
    # CONTEXT-only world-news dots (GDELT GKG). Sidecar-only by design — it never reads
    # the DB or writes flags.json, so a news signal can NEVER mutate a computed number.
    from .gdelt_news import run as news_geo_run
    return news_geo_run(ctx)


def _quakes(ctx: EnrichCtx) -> dict:
    # CONTEXT-only earthquake dots (USGS M4+). Sidecar-only — same structural guarantee:
    # it never touches the DB or flags, so a quake can never move a computed number.
    from .quakes import run as quakes_run
    return quakes_run(ctx)


def _timeseries(ctx: EnrichCtx) -> dict:
    from .export_timeseries import export_timeseries
    r = export_timeseries(db_path=ctx.db_path, out_dir=ctx.out_dir)
    return {"name": "timeseries", "sidecar": "timeseries.json", "series": r.get("series")}


def _market(ctx: EnrichCtx) -> dict:
    from .business.market import run as market_run
    return market_run(ctx)


def _stress(ctx: EnrichCtx) -> dict:
    from .narrative.stress import run as stress_run
    return stress_run(ctx)


def _events(ctx: EnrichCtx) -> dict:
    from .narrative.events import run as events_run
    return events_run(ctx)


def _brief(ctx: EnrichCtx) -> dict:
    from .narrative.brief import run as brief_run
    return brief_run(ctx)


def _world(ctx: EnrichCtx) -> dict:
    from .narrative.world import run as world_run
    return world_run(ctx)


def _hazards(ctx: EnrichCtx) -> dict:
    from .hazards import run as hazards_run
    return hazards_run(ctx)


def _weather(ctx: EnrichCtx) -> dict:
    from .weather import run as weather_run
    return weather_run(ctx)


def _ports_lookup(ctx: EnrichCtx) -> dict:
    from .export_ports_lookup import run as lookup_run
    return lookup_run(ctx)


def _gatun(ctx: EnrichCtx) -> dict:
    from .gatun import run as gatun_run
    return gatun_run(ctx)


# (name, run(ctx)->receipt, depends_on_flags). New waves append here.
# ORDER MATTERS: stress reads timeseries.json; brief reads every sidecar above it.
ENRICHERS: list[tuple[str, Callable[[EnrichCtx], dict], bool]] = [
    ("exposure", _exposure, True),
    ("news", _news, True),
    ("hazards", _hazards, True),
    ("weather", _weather, True),       # live NHC+GDACS active storms -> flags' live_storm
    ("gatun", _gatun, False),
    ("news_geo", _news_geo, False),    # CONTEXT: GDELT world-news dots, sidecar-only
    ("quakes", _quakes, False),        # CONTEXT: USGS M4+ earthquakes, sidecar-only
    ("timeseries", _timeseries, False),
    ("ports_lookup", _ports_lookup, False),
    ("market", _market, True),
    ("stress", _stress, False),
    ("world", _world, False),
    ("events", _events, True),
    ("brief", _brief, True),
]


def run_enrichers(ctx: EnrichCtx) -> dict:
    """Run every registered enricher; swallow per-enricher failures."""
    receipts: dict[str, dict] = {}
    for name, run, _ in ENRICHERS:
        try:
            receipts[name] = run(ctx)
        except Exception as e:  # noqa: BLE001 — degrade, never abort publish
            receipts[name] = {"name": name, "error": repr(e)}
            log.warning("enricher %s failed: %r", name, e)
    return receipts


def build_ctx(db=None, out=None) -> EnrichCtx:
    """Build an EnrichCtx from the configured DB + publish dir (as_of from DuckDB)."""
    db = Path(db) if db else db_path()
    out = Path(out) if out else publish_dir()
    con = duckdb.connect(str(db), read_only=True)
    try:
        row = con.execute("SELECT max(date) FROM fct_chokepoint_daily").fetchone()
        as_of = str(row[0]) if row and row[0] is not None else ""
    finally:
        con.close()
    return EnrichCtx(db_path=db, out_dir=out, flags_path=out / "flags.json",
                     as_of=as_of, today=date.today().isoformat())
