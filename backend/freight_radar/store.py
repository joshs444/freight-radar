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
                # SPINE provenance edge — the measured root has null; the rest name their parent
                "derives_from": d.derives_from,
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
    # read the layer's sidecar by its output stem, or by its id (so core layers like flags /
    # snapshot, which carry no enricher `output`, are still groundable from <id>.json)
    payload = _read(out, d.output or d.id)
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


VERIFY_DISCLAIMER = (
    "verify() returns a lineage lookup or ABSTAINS — never a true/false verdict on a claim, "
    "never a confidence. The honest 'no' is the answer; an adjudicating boolean is centrum."
)


def _observation_for(payload: object, entity_id: Optional[str]) -> object:
    """The cited value to return as grounding. If the layer carries items and an entity is
    named, return the matching item; otherwise the layer-level fields (items elided to a
    count so the lineage stays compact)."""
    if not isinstance(payload, dict):
        return payload
    items = None
    for key in ("items", "events"):
        if isinstance(payload.get(key), list):
            items = payload[key]
            break
    if entity_id and items:
        for it in items:
            if isinstance(it, dict) and entity_id in (
                it.get("portid"),
                it.get("id"),
                it.get("entity"),
                it.get("port"),
                it.get("site"),
            ):
                return it
    # layer-level: keep the scalar provenance fields, summarise any big array to a count
    return {
        k: (f"[{len(v)} items]" if isinstance(v, list) else v)
        for k, v in payload.items()
        if k not in ("disclaimer",)
    }


def verify(claim_layer: str, entity_id: Optional[str] = None, out_dir=None) -> dict:
    """The honest grounding check an agent calls BEFORE asserting a claim.

    Does the Standpoint store hold a CITED OBSERVATION for ``claim_layer`` (optionally narrowed
    to ``entity_id``)? Returns the observation **with full provenance** when grounded, else
    ABSTAINS. It never returns a true/false verdict and never a confidence — the honest "no"
    ("no measured observation supports this") is the product. An agent uses an abstain to
    **suppress** an ungrounded claim. A claim referencing something the store does not measure
    (a geopolitics narrative, a forecast) abstains with ``in_scope=False`` — Standpoint refuses
    the judgment seat rather than adjudicating it.
    """
    d = next((x for x in REGISTRY if x.id == claim_layer), None)
    if d is None:
        return {
            "result": "abstain",
            "grounded": False,
            "in_scope": False,
            "reason": (
                f"no layer '{claim_layer}' in the store — no measured observation supports this"
            ),
            "disclaimer": VERIFY_DISCLAIMER,
        }
    out = _store_dir(out_dir)
    payload = _read(out, d.output or d.id)  # core layers (flags/snapshot) ground from <id>.json
    if payload is None:
        return {
            "result": "abstain",
            "grounded": False,
            "in_scope": True,
            "reason": (
                f"layer '{claim_layer}' is in scope but currently absent (degraded-to-dark) — "
                "nothing to cite"
            ),
            "disclaimer": VERIFY_DISCLAIMER,
        }
    return {
        "result": "grounded",
        "grounded": True,
        "in_scope": True,
        "layer": d.id,
        "tier": d.kind.value,
        "metric": d.metric,
        "source": (
            {"name": d.source.name, "url": d.source.url, "license": d.source.license}
            if d.source
            else None
        ),
        "as_of": (payload.get("as_of") or payload.get("generated_at")) if isinstance(payload, dict) else None,
        "observation": _observation_for(payload, entity_id),
        "disclaimer": VERIFY_DISCLAIMER,
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


def _flag_for_portid(out: Path, portid: str):
    """The active flag at a portid (lifecycle != resolved), or None — used to fold a flagged
    entity's OWN attached evidence into nearby()."""
    flags = _read(out, "flags")
    if not isinstance(flags, list):
        return None
    for f in flags:
        if isinstance(f, dict) and f.get("portid") == portid and f.get("lifecycle") != "resolved":
            return f
    return None


def _flag_attached_evidence(out: Path, flag: dict) -> dict:
    """ZONE 1 place-attributable evidence for a flagged entity: its OWN cited news (news.json keyed
    by flag_id) + live_storm + official_event — the SAME fold-in the frontend NearbyPanel does, so
    the agent surface tells the identical 'here, specifically' story. Association only."""
    fid = flag.get("flag_id")
    news_doc = _read(out, "news")
    articles = []
    if isinstance(news_doc, dict):
        entry = (news_doc.get("items") or {}).get(fid) or {}
        for a in entry.get("items", []) or []:
            articles.append(
                {
                    "title": a.get("title"),
                    "url": a.get("url"),
                    "source": a.get("source"),
                    "published": a.get("published"),
                }
            )
    return {
        "flag_id": fid,
        "entity": flag.get("entity"),
        "news": articles,
        "live_storm": flag.get("live_storm"),
        "official_event": flag.get("official_event"),
        "disclaimer": ASSOCIATION_ONLY,
    }


def _national_context(out: Path):
    """ZONE 2 — the fenced national/global signals (signals_fdr.json, fdr_significant + national).
    Place-INVARIANT by construction: a pure function of the global file, identical for every query,
    NEVER distance-tagged, NEVER attributed to a point. Returns None when there are no signals."""
    doc = _read(out, "signals_fdr")
    if not isinstance(doc, dict):
        return None
    sig = [
        s
        for s in (doc.get("items") or [])
        if isinstance(s, dict) and s.get("fdr_significant") and s.get("fenced") == "national"
    ]
    sig.sort(key=lambda s: abs(s.get("our_zscore") or 0.0), reverse=True)
    if not sig:
        return None
    return {
        "note": (
            "National/global measured anomalies — a z-score we compute over cited public indices, "
            "FDR-controlled. Place-INVARIANT: identical for every place, never distance-tagged, "
            "never attributed to this point."
        ),
        "disclaimer": "Association only, never a stated cause.",
        "signals": [
            {
                "name": s.get("name"),
                "family": s.get("family"),
                "our_zscore": s.get("our_zscore"),
                "source": s.get("source"),
                "source_url": s.get("source_url"),
                "as_of": s.get("as_of"),
            }
            for s in sig
        ],
    }


def nearby(
    lat: float, lon: float, radius_km: float = 750.0, portid: str | None = None, out_dir=None
) -> dict:
    """CONTEXT facts within `radius_km` of a point, ordered ONLY by distance — the two-zone
    'what's near here' surface (mirrors the frontend NearbyPanel).

    `items` is ZONE 1's co-located cited context: never a score, a severity ranking, or a stated
    cause; every item carries its source + distance. When `portid` names an active flagged entity,
    `here_specifically` folds in that flag's OWN cited news + live_storm + official_event. ZONE 2's
    `national_context` is the fenced national/global signal set — place-INVARIANT, never attributed
    to this point. Co-location is association at every layer.
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
    result = {
        "query": {"lat": lat, "lon": lon, "radius_km": radius_km, "portid": portid},
        "disclaimer": ASSOCIATION_ONLY,
        "count": len(hits),
        "items": hits,
    }
    # ZONE 1 fold-in: a flagged entity's own attached evidence (news/storm/event)
    if portid:
        flag = _flag_for_portid(out, portid)
        if flag:
            result["here_specifically"] = _flag_attached_evidence(out, flag)
    # ZONE 2: the fenced national band — added only when there are signals (keeps tmp-dir reads lean)
    nat = _national_context(out)
    if nat:
        result["national_context"] = nat
    return result


def write_catalog(out_dir=None) -> Path:
    """Materialize catalog.json — the agent/browser entry point — into <store>/."""
    out = _store_dir(out_dir) / "store"
    out.mkdir(parents=True, exist_ok=True)
    p = out / "catalog.json"
    p.write_text(json.dumps(catalog(out_dir), indent=2) + "\n")
    return p


if __name__ == "__main__":
    print(json.dumps(catalog(), indent=2))
