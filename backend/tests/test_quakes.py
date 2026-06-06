"""The USGS earthquake layer's honesty contract — same machine-enforced rail as news_geo.

A context layer: registered on the enricher registry, sidecar-only (never the WAP fact
path), and free of any causal/forecast verb in its copy (backend + the frontend quake
lines). A quake is shown as a co-located, co-timed fact the reader weighs — never a
stated cause of a freight number.
"""

from __future__ import annotations

from pathlib import Path

import freight_radar.publish as publish
from freight_radar import quakes as q
from freight_radar.enrich import ENRICHERS
from freight_radar.honesty.lexicon import CAUSAL_FORECAST as CAUSAL  # one shared banned list

REPO = Path(__file__).resolve().parents[2]
FRONTEND = REPO / "frontend" / "src"


def test_quakes_is_registered_context_sidecar_only():
    entry = next((e for e in ENRICHERS if e[0] == "quakes"), None)
    assert entry is not None, "quakes must be on the enricher registry"
    assert entry[2] is False, "quakes is independent of flags (depends_on_flags=False)"
    assert "quakes" in publish._SIDECARS, "quakes must be a reported sidecar"


def test_quakes_never_touches_the_fact_path():
    src = (REPO / "backend" / "freight_radar" / "quakes.py").read_text()
    for forbidden in ("duckdb", "fct_", "flags_path", "flags.json"):
        assert forbidden not in src, f"quakes must not touch {forbidden}"


def test_quakes_backend_copy_has_no_causal_verbs():
    src = (REPO / "backend" / "freight_radar" / "quakes.py").read_text().lower()
    hits = [v for v in CAUSAL if v in src]
    assert not hits, f"causal/forecast verb in quakes backend copy: {hits}"


def test_quakes_frontend_copy_has_no_causal_verbs():
    offenders: list[str] = []
    for f in ("Globe.tsx", "components/LayerPanel.tsx"):
        for ln in (FRONTEND / f).read_text().splitlines():
            low = ln.lower()
            if "quake" in low or "usgs" in low or "seismic" in low:
                offenders += [f"{f}: {ln.strip()}" for v in CAUSAL if v in low]
    assert not offenders, f"causal/forecast verb in quake layer copy: {offenders}"


def test_filter_and_shape():
    feats = [
        {"id": "a", "properties": {"mag": 6.1, "place": "Off Tonga", "time": 1780000000000,
                                   "tsunami": 1, "url": "https://usgs/a"},
         "geometry": {"coordinates": [-172.2, -17.6, 10.0]}},
        {"id": "b", "properties": {"mag": 3.2, "place": "weak", "time": 1780000000000},
         "geometry": {"coordinates": [1.0, 2.0, 5.0]}},          # below MIN_MAG -> drop
        {"id": "c", "properties": {"mag": 5.0, "place": "noxy", "time": 1780000000000},
         "geometry": {"coordinates": [None, None]}},             # no coords -> drop
    ]

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"features": feats}

    import contextlib

    @contextlib.contextmanager
    def fake_client(*a, **k):
        yield object()

    q._http.client = fake_client          # type: ignore[attr-defined]
    q._http.get = lambda *a, **k: Resp()  # type: ignore[attr-defined]

    items = q._collect()
    assert len(items) == 1
    it = items[0]
    assert it["id"] == "a" and it["mag"] == 6.1 and it["tsunami"] is True
    assert (it["lat"], it["lon"], it["depth_km"]) == (-17.6, -172.2, 10.0)
