"""The authoritative layer registry — one `LayerDescriptor` per layer.

This is the hub-and-spoke honesty model made into data (STANDPOINT-VISION.md §2, §4).
Every layer the app ships is one row below, stamped with:

  * **kind** — its epistemic tier: SPINE (we own the full chain), SIGNAL (we compute a
    Python scalar over raw inputs), CONTEXT (someone else's cited value shown as-is).
    `kind` drives the import-graph firewall: a SIGNAL/CONTEXT layer that imports the
    detector / fact-table writers fails CI (test_layer_firewall.py).
  * **producer** — how its data is generated: the `enricher` loop, the `core` snapshot
    export, the off-loop AIS consumer, a separate `external` Action step (GFS wind), or
    pure `client` rendering (GIBS satellite, no data file).
  * the **sidecar** it writes and the **frontend** toggle/fetch metadata.

The three lists that used to be hand-maintained are now DERIVED from `REGISTRY`:
  * `enrich.ENRICHERS`  == `ENRICHERS` here (the enricher tuples, in pipeline order);
  * `publish._SIDECARS` == `SIDECARS` here (the optional-sidecar freshness set);
  * the TS `LayerId` union + panel + defaults == `codegen.render_ts()`.

Adding or modifying a layer is a single append/edit here — the byte-identical golden
masters (test_golden_sidecars.py) prove the refactor changed no number.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Callable, Optional


# --- the context every enricher receives ------------------------------------
@dataclass
class EnrichCtx:
    """The handle passed to every enricher's ``run(ctx)``.

    A CONTEXT/SIGNAL enricher gets ``flags_path`` to *read* the published flags (and,
    for the few that corroborate, to attach an annotation field) — but it can never
    import the detector that *computes* a flag. That boundary is the firewall.
    """

    db_path: Path
    out_dir: Path
    flags_path: Path  # data/flags.json
    as_of: str  # snapshot max date 'YYYY-MM-DD'
    today: str  # 'YYYY-MM-DD'


# --- the epistemic + structural taxonomy ------------------------------------
class Kind(str, Enum):
    SPINE = "SPINE"  # exactly the freight chain: we own ingest -> facts -> detect -> index
    SIGNAL = "SIGNAL"  # a Python scalar we compute over raw observed inputs
    CONTEXT = "CONTEXT"  # someone else's cited raw value, shown as-is
    # DERIVED is reserved for the P6 reasoning agent — no layer carries it yet.


class Producer(str, Enum):
    CORE = "core"  # the snapshot/flags/lanes export — the spine's own payload
    ENRICHER = "enricher"  # runs inside run_enrichers()
    AIS = "ais"  # sidecar/ais_consumer.py — off the enricher loop
    EXTERNAL = "external"  # a separate Action step (GFS wind is heavy/slow)
    CLIENT = "client"  # rendered entirely client-side; no data file at all


@dataclass(frozen=True)
class Source:
    """Provenance + the zero-cost gate keys (seed of the P1 source_manifest)."""

    name: str
    url: str
    license: str
    auth: str = "none"  # none | free_key | oauth_free
    cost: str = "free"  # CI fails on anything but free


@dataclass(frozen=True)
class Globe:
    """Frontend toggle metadata for a layer that appears on the globe + panel."""

    layer_id: str  # the TS LayerId slug (may differ from the descriptor id)
    section: str  # "Freight" | "Context" — UI grouping, NOT the epistemic tier
    label: str
    swatch: str  # the CSS swatch class in LayerPanel
    default_on: bool
    order: int  # position within its section


@dataclass(frozen=True)
class LayerDescriptor:
    id: str
    kind: Kind
    producer: Producer
    # backend wiring
    module: Optional[str] = None  # the real producer module — the firewall analysis target
    run: Optional[Callable[[EnrichCtx], dict]] = None  # enricher adapter (producer==ENRICHER)
    enricher_name: Optional[str] = None  # ENRICHERS tuple[0]; defaults to id
    depends_on_flags: bool = False
    enrich_order: Optional[int] = None  # position in run_enrichers (producer==ENRICHER)
    output: Optional[str] = None  # the json stem it writes (None for core-read / client)
    manifest_sidecar: bool = False  # appears in publish._SIDECARS (optional freshness)
    # frontend wiring
    fetch_file: Optional[str] = None  # data/<x>.json useData loads into AppData (None = not in AppData)
    appdata_key: Optional[str] = None  # the AppData field name (camelCase) if fetched
    globe: Optional[Globe] = None  # globe-toggle metadata (None = not a toggle)
    # provenance / honesty (seed of the source_manifest + the brand)
    metric: Optional[str] = None  # the owned statistic + method (None for passthrough CONTEXT)
    source: Optional[Source] = None
    honesty_note: Optional[str] = None

    @property
    def enrich_key(self) -> str:
        return self.enricher_name or self.id


# --- adapters: wrap each enricher to the (ctx)->receipt interface ------------
# (moved verbatim from enrich.py; each lazy-imports its real module so importing
#  the registry stays cheap and never drags in heavy deps.)
def _exposure(ctx: EnrichCtx) -> dict:
    from ..business.exposure import enrich_from_files

    s = enrich_from_files(flags_path=ctx.flags_path, out_dir=ctx.out_dir, db=ctx.db_path)
    return {
        "name": "exposure",
        "sidecar": "exposure.json",
        "exposed_value_usd": s.get("exposed_value_usd"),
        "coverage_pct": s.get("coverage_pct"),
        "disruptions": s.get("active_disruptions_hitting_you"),
    }


def _news(ctx: EnrichCtx) -> dict:
    from ..business.news import enrich_news_from_files

    p = enrich_news_from_files(
        flags_path=ctx.flags_path, out_dir=ctx.out_dir, today=date.fromisoformat(ctx.today)
    )
    return {"name": "news", "sidecar": "news.json", "flags": len(p.get("items", {}))}


def _news_geo(ctx: EnrichCtx) -> dict:
    # CONTEXT-only world-news dots (GDELT GKG). Sidecar-only by design — it never reads
    # the DB or writes flags.json, so a news signal can NEVER mutate a computed number.
    from ..gdelt_news import run as news_geo_run

    return news_geo_run(ctx)


def _quakes(ctx: EnrichCtx) -> dict:
    # CONTEXT-only earthquake dots (USGS M4+). Sidecar-only — same structural guarantee:
    # it never touches the DB or flags, so a quake can never move a computed number.
    from ..quakes import run as quakes_run

    return quakes_run(ctx)


def _timeseries(ctx: EnrichCtx) -> dict:
    from ..export_timeseries import export_timeseries

    r = export_timeseries(db_path=ctx.db_path, out_dir=ctx.out_dir)
    return {"name": "timeseries", "sidecar": "timeseries.json", "series": r.get("series")}


def _market(ctx: EnrichCtx) -> dict:
    from ..business.market import run as market_run

    return market_run(ctx)


def _stress(ctx: EnrichCtx) -> dict:
    from ..narrative.stress import run as stress_run

    return stress_run(ctx)


def _events(ctx: EnrichCtx) -> dict:
    from ..narrative.events import run as events_run

    return events_run(ctx)


def _brief(ctx: EnrichCtx) -> dict:
    from ..narrative.brief import run as brief_run

    return brief_run(ctx)


def _world(ctx: EnrichCtx) -> dict:
    from ..narrative.world import run as world_run

    return world_run(ctx)


def _hazards(ctx: EnrichCtx) -> dict:
    from ..hazards import run as hazards_run

    return hazards_run(ctx)


def _weather(ctx: EnrichCtx) -> dict:
    from ..weather import run as weather_run

    return weather_run(ctx)


def _ports_lookup(ctx: EnrichCtx) -> dict:
    from ..export_ports_lookup import run as lookup_run

    return lookup_run(ctx)


def _gatun(ctx: EnrichCtx) -> dict:
    from ..gatun import run as gatun_run

    return gatun_run(ctx)


def _commodities(ctx: EnrichCtx) -> dict:
    from ..commodities import run as commodities_run

    return commodities_run(ctx)


def _streamflow(ctx: EnrichCtx) -> dict:
    from ..streamflow import run as streamflow_run

    return streamflow_run(ctx)


def _space_weather(ctx: EnrichCtx) -> dict:
    from ..space_weather import run as space_weather_run

    return space_weather_run(ctx)


def _eonet(ctx: EnrichCtx) -> dict:
    from ..eonet import run as eonet_run

    return eonet_run(ctx)


# --- THE REGISTRY -----------------------------------------------------------
# One row per layer. Order here is read top-to-bottom for the manifest; the
# enricher pipeline order is set explicitly by `enrich_order` (NOT list position),
# preserving the exact, dependency-correct run order (stress reads timeseries; brief
# reads every sidecar above it).
REGISTRY: tuple[LayerDescriptor, ...] = (
    # ---- SPINE core: the freight payload (snapshot / flags / lanes) ----
    LayerDescriptor(
        id="snapshot",
        kind=Kind.SPINE,
        producer=Producer.CORE,
        module="freight_radar.export_snapshot",
        fetch_file="data/snapshot.json",
        appdata_key="snapshot",
        metric="per-chokepoint throughput vs STL baseline (z-score, % change)",
        source=Source("IMF PortWatch", "https://portwatch.imf.org", "PortWatch terms"),
        honesty_note="Computed in Python from cited PortWatch AIS-derived port calls.",
    ),
    LayerDescriptor(
        id="flags",
        kind=Kind.SPINE,
        producer=Producer.CORE,
        module="freight_radar.detect.run_detection",
        fetch_file="data/flags.json",
        appdata_key="flags",
        globe=Globe("flags", "Freight", "flagged", "pulse", True, 0),
        metric="gated change-point + z-score disruption flags",
    ),
    LayerDescriptor(
        id="chokepoints",
        kind=Kind.SPINE,
        producer=Producer.CORE,
        module="freight_radar.export_snapshot",
        globe=Globe("chokepoints", "Freight", "chokepoints", "amber", True, 1),
    ),
    LayerDescriptor(
        id="ports",
        kind=Kind.SPINE,
        producer=Producer.CORE,
        module="freight_radar.export_snapshot",
        globe=Globe("ports", "Freight", "ports", "port", True, 2),
    ),
    LayerDescriptor(
        id="lanes",
        kind=Kind.SPINE,
        producer=Producer.CORE,
        module="freight_radar.export_snapshot",
        fetch_file="data/lanes.json",
        appdata_key="lanes",
        globe=Globe("lanes", "Freight", "lanes", "lane", True, 4),
    ),
    # ---- enrichers (run inside run_enrichers, in enrich_order) ----
    LayerDescriptor(
        id="exposure",
        kind=Kind.SIGNAL,
        producer=Producer.ENRICHER,
        module="freight_radar.business.exposure",
        run=_exposure,
        depends_on_flags=True,
        enrich_order=0,
        output="exposure",
        manifest_sidecar=True,
        fetch_file="data/exposure.json",
        appdata_key="exposure",
        metric="exposed trade value & banded cost-of-disruption (USD)",
        source=Source(
            "sample/user trade flows (samples/business_flows.csv)",
            "https://github.com/joshs444/freight-radar",
            "illustrative sample / user-provided",
        ),
    ),
    LayerDescriptor(
        id="news",
        kind=Kind.CONTEXT,
        producer=Producer.ENRICHER,
        module="freight_radar.business.news",
        run=_news,
        depends_on_flags=True,
        enrich_order=1,
        output="news",
        manifest_sidecar=True,
        fetch_file="data/news.json",
        appdata_key="news",
        source=Source("Google News RSS", "https://news.google.com", "Google News terms"),
        honesty_note="Per-flag cited headlines — possibly related, never a stated cause.",
    ),
    LayerDescriptor(
        id="disruptions",
        kind=Kind.CONTEXT,
        producer=Producer.ENRICHER,
        module="freight_radar.hazards",
        run=_hazards,
        enricher_name="hazards",
        depends_on_flags=True,
        enrich_order=2,
        output="disruptions",
        manifest_sidecar=True,
        fetch_file="data/disruptions.json",
        appdata_key="disruptions",
        source=Source("GDACS", "https://www.gdacs.org", "GDACS terms"),
        honesty_note="Cited official hazard alerts; corroborates a flag, never creates one.",
    ),
    LayerDescriptor(
        id="weather",
        kind=Kind.CONTEXT,
        producer=Producer.ENRICHER,
        module="freight_radar.weather",
        run=_weather,
        depends_on_flags=True,
        enrich_order=3,
        output="weather",
        manifest_sidecar=True,
        fetch_file="data/weather.json",
        appdata_key="weather",
        globe=Globe("storms", "Context", "storms", "storm", True, 2),
        source=Source("NHC / GDACS", "https://www.nhc.noaa.gov", "public domain"),
    ),
    LayerDescriptor(
        id="gatun",
        kind=Kind.SIGNAL,
        producer=Producer.ENRICHER,
        module="freight_radar.gatun",
        run=_gatun,
        enrich_order=4,
        output="gatun",
        manifest_sidecar=True,
        fetch_file="data/gatun.json",
        appdata_key="gatun",
        metric="Gatún lake level percentile -> min projected Neopanamax draft (ft)",
        source=Source("Panama Canal Authority", "https://pancanal.com", "ACP terms"),
    ),
    LayerDescriptor(
        id="news_geo",
        kind=Kind.CONTEXT,
        producer=Producer.ENRICHER,
        module="freight_radar.gdelt_news",
        run=_news_geo,
        enrich_order=5,
        output="news_geo",
        manifest_sidecar=True,
        fetch_file="data/news_geo.json",
        appdata_key="newsGeo",
        globe=Globe("news", "Context", "news", "news", True, 0),
        source=Source("GDELT 2.0 GKG", "https://www.gdeltproject.org", "GDELT terms"),
        honesty_note="Geo-tagged article dots; possibly related context, not a stated cause.",
    ),
    LayerDescriptor(
        id="quakes",
        kind=Kind.CONTEXT,
        producer=Producer.ENRICHER,
        module="freight_radar.quakes",
        run=_quakes,
        enrich_order=6,
        output="quakes",
        manifest_sidecar=True,
        fetch_file="data/quakes.json",
        appdata_key="quakes",
        globe=Globe("quakes", "Context", "earthquakes", "quake", False, 1),
        source=Source("USGS", "https://earthquake.usgs.gov", "public domain"),
    ),
    LayerDescriptor(
        id="timeseries",
        kind=Kind.SPINE,
        producer=Producer.ENRICHER,
        module="freight_radar.export_timeseries",
        run=_timeseries,
        enrich_order=7,
        output="timeseries",
        manifest_sidecar=True,
        fetch_file="data/timeseries.json",
        appdata_key="timeseries",
    ),
    LayerDescriptor(
        id="ports_lookup",
        kind=Kind.SPINE,
        producer=Producer.ENRICHER,
        module="freight_radar.export_ports_lookup",
        run=_ports_lookup,
        enrich_order=8,
        output="ports_lookup",
        manifest_sidecar=True,
        # not in AppData — fetched lazily on demand (Upload / DataFeed), not by useData.
    ),
    LayerDescriptor(
        id="market",
        kind=Kind.CONTEXT,
        producer=Producer.ENRICHER,
        module="freight_radar.business.market",
        run=_market,
        depends_on_flags=True,
        enrich_order=9,
        output="market",
        manifest_sidecar=True,
        fetch_file="data/market.json",
        appdata_key="market",
        source=Source(
            "FRED (St. Louis Fed) + Stooq",
            "https://fred.stlouisfed.org",
            "public domain (FRED) / Stooq terms",
        ),
        honesty_note="Cited market indicators shown as published; never restated as ours.",
    ),
    LayerDescriptor(
        id="stress",
        kind=Kind.SPINE,
        producer=Producer.ENRICHER,
        module="freight_radar.narrative.stress",
        run=_stress,
        enrich_order=10,
        output="stress",
        manifest_sidecar=True,
        fetch_file="data/stress.json",
        appdata_key="stress",
        metric="Global Ocean Freight Stress Index (0-100): economic-weighted breadth + worst-chokepoint depth",
    ),
    LayerDescriptor(
        id="world",
        kind=Kind.SPINE,
        producer=Producer.ENRICHER,
        module="freight_radar.narrative.world",
        run=_world,
        enrich_order=11,
        output="world",
        manifest_sidecar=True,
        fetch_file="data/world.json",
        appdata_key="world",
    ),
    LayerDescriptor(
        id="events",
        kind=Kind.SPINE,
        producer=Producer.ENRICHER,
        module="freight_radar.narrative.events",
        run=_events,
        depends_on_flags=True,
        enrich_order=12,
        output="events",
        manifest_sidecar=True,
        fetch_file="data/events.json",
        appdata_key="events",
    ),
    LayerDescriptor(
        id="brief",
        kind=Kind.SPINE,
        producer=Producer.ENRICHER,
        module="freight_radar.narrative.brief",
        run=_brief,
        depends_on_flags=True,
        enrich_order=13,
        output="brief",
        manifest_sidecar=True,
        fetch_file="data/brief.json",
        appdata_key="brief",
    ),
    LayerDescriptor(
        id="commodities",
        kind=Kind.SIGNAL,
        producer=Producer.ENRICHER,
        module="freight_radar.commodities",
        run=_commodities,
        enrich_order=14,
        output="commodities",
        manifest_sidecar=True,
        # not in AppData — queryable via the read surface (catalog / MCP / SQL console).
        metric="12-month rolling z-score of a cited commodity price (the anomaly we compute)",
        source=Source(
            "FRED (public domain · IMF Primary Commodity Prices)",
            "https://fred.stlouisfed.org",
            "public domain",
        ),
        honesty_note="We compute the z-score anomaly; the price stays cited context, never restated as ours.",
    ),
    LayerDescriptor(
        id="streamflow",
        kind=Kind.CONTEXT,
        producer=Producer.ENRICHER,
        module="freight_radar.streamflow",
        run=_streamflow,
        enrich_order=15,
        output="streamflow",
        manifest_sidecar=True,
        source=Source("USGS Water Services", "https://waterservices.usgs.gov", "public domain"),
        honesty_note="Observed river stage shown as USGS publishes it; possibly-related context, never a cause.",
    ),
    LayerDescriptor(
        id="space_weather",
        kind=Kind.CONTEXT,
        producer=Producer.ENRICHER,
        module="freight_radar.space_weather",
        run=_space_weather,
        enrich_order=16,
        output="space_weather",
        manifest_sidecar=True,
        source=Source("NOAA SWPC", "https://www.swpc.noaa.gov", "public domain"),
        honesty_note="Observed geomagnetic indices shown as NOAA publishes them; possibly-related context, never a cause.",
    ),
    LayerDescriptor(
        id="eonet",
        kind=Kind.CONTEXT,
        producer=Producer.ENRICHER,
        module="freight_radar.eonet",
        run=_eonet,
        enrich_order=17,
        output="eonet",
        manifest_sidecar=True,
        source=Source("NASA EONET", "https://eonet.gsfc.nasa.gov", "public domain"),
        honesty_note="Observed natural events (fire/volcano/storm/ice) shown as NASA tracks them; possibly-related context, never a cause.",
    ),
    # ---- off-loop producers ----
    LayerDescriptor(
        id="ships",
        kind=Kind.CONTEXT,
        producer=Producer.AIS,
        module="freight_radar.sidecar.ais_consumer",
        output="ships",
        manifest_sidecar=True,
        fetch_file="data/ships.json",
        appdata_key="ships",
        globe=Globe("ships", "Freight", "vessels", "ship", True, 3),
        source=Source("AISStream", "https://aisstream.io", "AISStream terms", auth="free_key"),
        honesty_note="A point-in-time AIS sample near the chokepoints — observed, not all ships.",
    ),
    LayerDescriptor(
        id="wind",
        kind=Kind.CONTEXT,
        producer=Producer.EXTERNAL,  # heavy GFS decode — a separate Action step, not run_enrichers
        module="freight_radar.wind",
        output="wind",
        manifest_sidecar=True,
        fetch_file="data/wind.json",
        appdata_key="wind",
        globe=Globe("wind", "Context", "wind", "wind", True, 3),
        source=Source("NOAA GFS", "https://nomads.ncep.noaa.gov", "public domain"),
    ),
    LayerDescriptor(
        id="satellite",
        kind=Kind.CONTEXT,
        producer=Producer.CLIENT,  # pure GIBS raster, rendered client-side — no data file
        globe=Globe("satellite", "Context", "satellite", "sat", False, 4),
        source=Source("NASA GIBS (VIIRS)", "https://gibs.earthdata.nasa.gov", "public domain"),
    ),
)


# --- derived views (the single source the old hand-lists become) ------------
ENRICHERS: list[tuple[str, Callable[[EnrichCtx], dict], bool]] = [
    (d.enrich_key, d.run, d.depends_on_flags)  # type: ignore[misc]
    for d in sorted(
        (d for d in REGISTRY if d.producer is Producer.ENRICHER),
        key=lambda d: d.enrich_order,  # type: ignore[arg-type,return-value]
    )
]

# The optional-sidecar freshness set publish.write_manifest reports (was a hand tuple).
SIDECARS: tuple[str, ...] = tuple(d.output for d in REGISTRY if d.manifest_sidecar and d.output)


def by_id(layer_id: str) -> LayerDescriptor:
    for d in REGISTRY:
        if d.id == layer_id:
            return d
    raise KeyError(layer_id)


def globe_descriptors() -> list[LayerDescriptor]:
    """Descriptors that render a toggleable globe layer, in (section, order) order."""
    g = [d for d in REGISTRY if d.globe is not None]
    sections = ["Freight", "Context"]
    return sorted(g, key=lambda d: (sections.index(d.globe.section), d.globe.order))  # type: ignore[union-attr]


def to_json() -> dict:
    """The serializable view codegen.py renders the TS from (no callables)."""
    return {
        "layers": [
            {
                "id": d.id,
                "kind": d.kind.value,
                "producer": d.producer.value,
                "output": d.output,
                "manifest_sidecar": d.manifest_sidecar,
                "fetch_file": d.fetch_file,
                "appdata_key": d.appdata_key,
                "is_core_fetch": d.producer is Producer.CORE and bool(d.fetch_file),
                "globe": (
                    {
                        "layer_id": d.globe.layer_id,
                        "section": d.globe.section,
                        "label": d.globe.label,
                        "swatch": d.globe.swatch,
                        "default_on": d.globe.default_on,
                        "order": d.globe.order,
                    }
                    if d.globe
                    else None
                ),
            }
            for d in REGISTRY
        ]
    }


# --- import-time invariants (cheap structural guards) -----------------------
def _validate() -> None:
    ids = [d.id for d in REGISTRY]
    assert len(ids) == len(set(ids)), f"duplicate descriptor ids: {ids}"

    enr = [d for d in REGISTRY if d.producer is Producer.ENRICHER]
    for d in enr:
        assert d.run is not None, f"{d.id}: ENRICHER must have a run()"
        assert d.enrich_order is not None, f"{d.id}: ENRICHER must have enrich_order"
        assert d.module is not None, f"{d.id}: ENRICHER must declare its module (firewall)"
    orders = sorted(d.enrich_order for d in enr)  # type: ignore[type-var]
    assert orders == list(range(len(enr))), f"enrich_order must be contiguous 0..n: {orders}"

    for d in REGISTRY:
        if d.manifest_sidecar:
            assert d.output, f"{d.id}: manifest_sidecar requires an output stem"
        if d.fetch_file:
            assert d.appdata_key, f"{d.id}: fetch_file requires an appdata_key"

    globe_ids = [d.globe.layer_id for d in REGISTRY if d.globe]  # type: ignore[union-attr]
    assert len(globe_ids) == len(set(globe_ids)), f"duplicate globe layer_ids: {globe_ids}"


_validate()
