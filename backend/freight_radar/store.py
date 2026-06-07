"""The agent-legible read surface over the published store (P1.5).

A pure, **read-only** API: it reads the sidecars the pipeline already publishes + the
registry, and returns facts *with their provenance* (tier · source · method · as_of). It
can never mutate the store — there is no write function here, by construction (a test
asserts it). This is the generalization of the chat's grounding into something an agent
(or the DuckDB-WASM browser surface, or a read-only MCP server) can consume.

  * `catalog()`     — the entry point: every layer's tier/kind/source/metric/honesty +
                      where its data lives. An agent reads this first to learn the store.
  * `get_layer(id)` — a layer's published payload, wrapped with its provenance.
  * `nearby(...)`   — co-located CONTEXT facts within a radius, ordered ONLY by distance,
                      stamped association-only (never a cause). A safe spatial primitive.

The store stays honest for a machine for the same reason it is for a human: clean tiers,
complete provenance, and no cross-layer causation baked in as a fact.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Optional

from .config import publish_dir
from .contracts import SIDECAR_CONTRACTS
from .registry.layers import REGISTRY

ASSOCIATION_ONLY = "Co-located in space/time — association only, never a stated cause."


def _store_dir(out_dir=None) -> Path:
    return Path(out_dir) if out_dir else publish_dir()


def _read(out: Path, name: str) -> Optional[object]:
    p = out / f"{name}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def catalog(out_dir=None) -> dict:
    """The agent's entry map: every layer, tier-stamped, with provenance + where to read it."""
    layers = []
    for d in REGISTRY:
        layers.append(
            {
                "id": d.id,
                "kind": d.kind.value,  # SPINE | SIGNAL | CONTEXT
                "producer": d.producer.value,
                "metric": d.metric,  # the owned statistic (null for passthrough CONTEXT)
                "sidecar": (f"data/{d.output}.json" if d.output else None),
                "globe_layer": (d.globe.layer_id if d.globe else None),
                # whether this feed's shape is machine-checked every refresh by the upstream
                # drift detector (freight_radar/contracts.py) — schema/liveness, not value
                "contract_monitored": bool(d.output and d.output in SIDECAR_CONTRACTS),
                "source": (
                    {
                        "name": d.source.name,
                        "url": d.source.url,
                        "license": d.source.license,
                        "auth": d.source.auth,
                        "cost": d.source.cost,
                    }
                    if d.source
                    else None
                ),
                "honesty_note": d.honesty_note,
            }
        )
    return {
        "schema_version": 1,
        "description": (
            "Read-only, tier-stamped catalog of the Standpoint store. measured = we computed "
            "the number in Python (SPINE: the freight chain; SIGNAL: an owned scalar). context "
            "= a cited raw value shown as-is. No value here was produced by a model in the "
            "number path; co-location is association, never a stated cause."
        ),
        "tiers": {
            "SPINE": "the freight chain we own end-to-end (ingest -> facts -> detect -> index)",
            "SIGNAL": "a Python scalar we compute over raw observed inputs",
            "CONTEXT": "someone else's cited raw value, shown as-is",
            "DERIVED": "an AI agent's commentary over the store — cited, association-only, owns no number",
        },
        "counts": {
            "layers": len(layers),
            "by_tier": {
                t: sum(1 for x in layers if x["kind"] == t)
                for t in ("SPINE", "SIGNAL", "CONTEXT", "DERIVED")
            },
        },
        "layers": layers,
    }


def get_layer(layer_id: str, out_dir=None) -> dict:
    """A layer's published payload, wrapped with its registry provenance (read-only)."""
    d = next((x for x in REGISTRY if x.id == layer_id), None)
    if d is None:
        raise KeyError(layer_id)
    out = _store_dir(out_dir)
    payload = _read(out, d.output) if d.output else None
    return {
        "id": d.id,
        "kind": d.kind.value,
        "metric": d.metric,
        "source": (
            {"name": d.source.name, "url": d.source.url, "license": d.source.license}
            if d.source
            else None
        ),
        "honesty_note": d.honesty_note,
        "present": payload is not None,
        "payload": payload,
    }


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


# CONTEXT layers that carry geo-located point items we can place near a spine entity.
_NEARBY_SOURCES = (
    ("quakes", "items", "USGS earthquake"),
    ("news_geo", "items", "GDELT news"),
    ("weather", "storms", "active storm"),
    ("eonet", "items", "NASA natural event"),
    ("marine", "items", "sea state"),
    ("tides", "items", "water level"),
    ("streamflow", "items", "river stage"),
    ("disruptions", "events", "GDACS hazard alert"),
)

# the per-item key that names a place, in priority order (layers disagree on the field name)
_PLACE_KEYS = ("place", "name", "port", "title", "river")


def nearby(lat: float, lon: float, radius_km: float = 750.0, out_dir=None) -> dict:
    """CONTEXT facts within `radius_km` of a point, ordered ONLY by distance.

    A safe spatial read primitive: it returns cited, co-located context — never a score,
    a ranking by severity, or a stated cause. Every item carries its source + distance.
    """
    out = _store_dir(out_dir)
    hits = []
    for layer_id, key, label in _NEARBY_SOURCES:
        data = _read(out, layer_id)
        if not isinstance(data, dict):
            continue
        items = data.get(key) or []
        src = data.get("source") or layer_id
        for it in items:
            if not isinstance(it, dict) or it.get("lat") is None or it.get("lon") is None:
                continue
            km = _haversine_km(lat, lon, float(it["lat"]), float(it["lon"]))
            if km <= radius_km:
                hits.append(
                    {
                        "layer": layer_id,
                        "kind": "CONTEXT",
                        "label": label,
                        "km": round(km, 1),
                        "source": src,
                        "place": next((it[k] for k in _PLACE_KEYS if it.get(k)), None),
                        "url": it.get("url"),
                        "detail": it,
                    }
                )
    hits.sort(key=lambda h: h["km"])  # distance only — no severity/evidence-density ranking
    return {
        "query": {"lat": lat, "lon": lon, "radius_km": radius_km},
        "disclaimer": ASSOCIATION_ONLY,
        "count": len(hits),
        "items": hits,
    }


def write_catalog(out_dir=None) -> Path:
    """Materialize catalog.json — the agent/browser entry point — into <store>/."""
    out = _store_dir(out_dir) / "store"
    out.mkdir(parents=True, exist_ok=True)
    p = out / "catalog.json"
    p.write_text(json.dumps(catalog(out_dir), indent=2) + "\n")
    return p


if __name__ == "__main__":
    print(json.dumps(catalog(), indent=2))
