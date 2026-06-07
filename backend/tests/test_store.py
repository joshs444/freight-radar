"""P1.5 — the agent-legible read surface is read-only, tier-stamped, and provenance-complete.

These gate the substrate-for-agents promise: the store exposes facts-with-provenance and
NO way to mutate them. The catalog is every layer tier-stamped; nearby is association-only
and distance-ordered (never a ranking — the centrum trap).
"""

from __future__ import annotations

import inspect
from pathlib import Path

from freight_radar import store
from freight_radar.registry.layers import REGISTRY


def test_catalog_is_complete_and_tier_stamped() -> None:
    cat = store.catalog()
    ids = {layer["id"] for layer in cat["layers"]}
    assert ids == {d.id for d in REGISTRY}, "catalog must list every registry layer"
    for layer in cat["layers"]:
        assert layer["kind"] in ("SPINE", "SIGNAL", "CONTEXT", "DERIVED"), layer
        # CONTEXT + DERIVED are passthrough/commentary — they own no computed metric.
        if layer["kind"] in ("CONTEXT", "DERIVED"):
            assert layer["metric"] is None, f"{layer['id']}: {layer['kind']} must not own a metric"
    assert cat["counts"]["layers"] == len(REGISTRY)


def test_get_layer_carries_provenance(tmp_path) -> None:
    # write a fake sidecar, prove get_layer wraps it with registry provenance
    (tmp_path / "quakes.json").write_text('{"items": [], "source": "USGS"}')
    got = store.get_layer("quakes", out_dir=tmp_path)
    assert got["id"] == "quakes"
    assert got["kind"] == "CONTEXT"
    assert got["source"]["name"]  # provenance present
    assert got["present"] is True


def test_nearby_is_association_only_and_distance_ordered(tmp_path) -> None:
    # two quakes at different distances from a point; nearby must order by distance only
    (tmp_path / "quakes.json").write_text(
        '{"source": "USGS", "items": ['
        '{"lat": 0.0, "lon": 5.0, "place": "far", "url": "u1"},'
        '{"lat": 0.0, "lon": 1.0, "place": "near", "url": "u2"}]}'
    )
    res = store.nearby(0.0, 0.0, radius_km=1000.0, out_dir=tmp_path)
    assert res["disclaimer"] == store.ASSOCIATION_ONLY
    assert [i["place"] for i in res["items"]] == ["near", "far"]  # distance order, not input order
    assert all(i["kind"] == "CONTEXT" for i in res["items"])  # only cited context, never the spine


def test_nearby_respects_radius(tmp_path) -> None:
    (tmp_path / "quakes.json").write_text(
        '{"source": "USGS", "items": [{"lat": 0.0, "lon": 80.0, "place": "very far", "url": "u"}]}'
    )
    res = store.nearby(0.0, 0.0, radius_km=500.0, out_dir=tmp_path)
    assert res["count"] == 0  # ~8900 km away, outside the radius


def test_store_surface_has_no_write_tool() -> None:
    # the read surface must expose NO mutation: no public function that writes/deletes the
    # store. (write_catalog only materializes the read-only catalog entry point.)
    public = [n for n, _ in inspect.getmembers(store, inspect.isfunction) if not n.startswith("_")]
    banned = {"set_layer", "put", "delete", "update_layer", "write_fact", "mutate", "ingest"}
    assert not (banned & set(public)), f"read surface exposes a mutator: {banned & set(public)}"


def test_verify_grounds_a_real_layer(tmp_path) -> None:
    (tmp_path / "tides.json").write_text(
        '{"as_of": "2026-06-07", "source": "NOAA", "items": ['
        '{"port": "Charleston", "lat": 0.0, "lon": 0.0, "water_level_ft": 3.0}]}'
    )
    r = store.verify("tides", "Charleston", out_dir=tmp_path)
    assert r["result"] == "grounded" and r["grounded"] is True
    assert r["observation"]["port"] == "Charleston"  # entity-narrowed, with the cited value
    assert "disclaimer" in r


def test_verify_abstains_loudly_on_an_unmeasured_claim(tmp_path) -> None:
    # a geopolitics/forecast claim names nothing the store measures → the honest "no"
    r = store.verify("tensions_escalating", out_dir=tmp_path)
    assert r["result"] == "abstain" and r["grounded"] is False and r["in_scope"] is False
    assert "no measured observation supports this" in r["reason"]


def test_verify_abstains_when_a_real_layer_is_dark(tmp_path) -> None:
    # the layer is in scope (registered) but its sidecar is absent (demoted/degraded)
    r = store.verify("tides", out_dir=tmp_path)  # no tides.json written
    assert r["result"] == "abstain" and r["in_scope"] is True and r["grounded"] is False


def test_verify_never_returns_a_truth_verdict() -> None:
    # result is only ever 'grounded' or 'abstain' — never a boolean true/false on the claim
    for layer in ("stress", "quakes", "not_a_real_layer"):
        r = store.verify(layer)
        assert r["result"] in ("grounded", "abstain")
        assert "true" not in r and "false" not in r and "confidence" not in r


def test_honest_no_demo_suppresses_the_ungrounded_claims() -> None:
    from freight_radar import verify_demo

    data = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"
    suppressed = verify_demo.run(data)
    assert suppressed >= 3  # the geopolitics + forecast + causal-attribution claims are dropped
