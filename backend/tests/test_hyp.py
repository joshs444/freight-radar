"""The hyp_* association tier — DARK by construction: BH-controlled, AssociationObj-shaped,
and fenced OFF the globe (the rendering firewall the plan demands before any math ships).

The import-graph fences (hyp can't reach the fact-writers; nothing imports hyp) live in
test_layer_firewall. Here: the math is BH-controlled + typed, and the RENDERING fence holds —
the globe's data path never references data/hyp/; only the SQL console (the DARK surface) does.
"""

from __future__ import annotations

import json
from pathlib import Path

from freight_radar.derived.contract import AssociationObj
from freight_radar.hyp.associate import associate

REPO = Path(__file__).resolve().parents[2]
PARQUET = REPO / "frontend" / "public" / "data" / "store" / "fct_observation.parquet"
FRONTEND = REPO / "frontend" / "src"


def test_associations_are_bh_controlled_and_typed() -> None:
    if not PARQUET.exists():
        import pytest

        pytest.skip("substrate parquet not built in this checkout")
    payload = associate(PARQUET)
    assert payload["tier"] == "HYP"
    c = payload["counts"]
    assert c["significant"] <= c["tested"]  # BH never invents significance
    assert c["expected_false"] == round(payload["q"] * c["significant"], 2)
    # every emitted row is admissible as the typed AssociationObj (validated stat + confounder)
    for it in payload["items"]:
        AssociationObj(
            layer_a=it["layer_a"],
            layer_b=it["layer_b"],
            method=it["method"],
            window="z-series",
            confounder_note=it["confounder_note"],
            lag=it["lag"],
        )
        assert it["method"] == "lead_lag" and abs(it["effect_size"]) <= 1.0


def test_the_rendering_fence_keeps_hyp_off_the_globe() -> None:
    # the globe renders from useData(AppData) + Globe.tsx — neither may touch data/hyp/, so a
    # DARK association can NEVER render co-located with a measured anomaly on the sphere.
    for f in ("lib/useData.ts", "Globe.tsx", "components/NearbyPanel.tsx"):
        src = (FRONTEND / f).read_text()
        assert "hyp/" not in src and "hyp_associations" not in src, f"{f} must not reach data/hyp/"
    # the DARK surface DOES exist — the SQL console is the only place it surfaces
    duck = (FRONTEND / "lib" / "duckdb.ts").read_text()
    assert "hyp/associations.json" in duck and "hyp_associations" in duck


def test_committed_associations_carry_the_dark_stamp() -> None:
    p = REPO / "frontend" / "public" / "data" / "hyp" / "associations.json"
    if not p.exists():
        import pytest

        pytest.skip("associations not generated in this checkout")
    d = json.loads(p.read_text())
    low = d["disclaimer"].lower()
    assert "never a cause" in low and "never a forecast" in low and "dark" in low
