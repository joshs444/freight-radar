"""AIS snapshot helpers — the pure, network-free bits (type mapping + bbox fallback)."""

from __future__ import annotations

from freight_radar.sidecar import ais_consumer as A


def test_ais_type_maps_coarse_classes():
    assert A._ais_type(70) == "cargo"      # 70-79 cargo
    assert A._ais_type(79) == "cargo"
    assert A._ais_type(80) == "tanker"     # 80-89 tanker
    assert A._ais_type(89) == "tanker"
    assert A._ais_type(60) == "passenger"  # 60-69 passenger
    assert A._ais_type(30) == "fishing"    # 30-39 fishing
    assert A._ais_type(0) == "vessel"      # unknown
    assert A._ais_type(None) == "vessel"   # missing -> safe default
    assert A._ais_type("not-a-number") == "vessel"


def test_chokepoint_bboxes_shape_and_fallback():
    # With no/real DB it must still return well-formed [[SW_lat,SW_lon],[NE_lat,NE_lon]] boxes
    boxes = A._chokepoint_bboxes(half=0.5)
    assert boxes and all(
        len(b) == 2 and len(b[0]) == 2 and len(b[1]) == 2 and b[0][0] < b[1][0] and b[0][1] < b[1][1]
        for b in boxes
    )
