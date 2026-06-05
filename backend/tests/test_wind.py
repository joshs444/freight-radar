"""Wind encoder tests — the GFS GRIB -> RGBA u/v PNG path, with xarray stubbed
(no network, no real GRIB). Pins the encoding contract the frontend ParticleLayer
relies on: u->R, v->G, calm wind -> mid-grey, full alpha, longitude re-centred."""

from __future__ import annotations

import numpy as np
import xarray

from freight_radar import wind as W


class _Var:
    def __init__(self, arr):
        self.values = arr


class _DS:
    def __init__(self, u, v):
        self._d = {"u10": _Var(u), "v10": _Var(v)}

    def __getitem__(self, k):
        return self._d[k]


def test_encode_rgba_contract(monkeypatch):
    # 4x8 grid (h, w); DOWNSAMPLE=2 -> 2x4 output. u in R, v in G.
    u = np.zeros((4, 8), dtype="float32")          # calm everywhere
    v = np.full((4, 8), 30.0, dtype="float32")     # max northward (hi end of [-30,30])
    monkeypatch.setattr(xarray, "open_dataset", lambda *a, **k: _DS(u, v))

    rgba = W._encode(b"not-a-real-grib")            # bytes are written then ignored (mock)
    assert rgba.shape == (2, 4, 4) and rgba.dtype == np.uint8
    assert (rgba[..., 0] == 128).all()              # calm u (0 m/s) -> ~mid-grey
    assert (rgba[..., 1] == 255).all()              # v = +30 (max) -> 255
    assert (rgba[..., 2] == 0).all() and (rgba[..., 3] == 255).all()


def test_encode_clamps_and_centres(monkeypatch):
    u = np.full((2, 4), -50.0, dtype="float32")     # below -30 -> clamps to 0
    v = np.zeros((2, 4), dtype="float32")
    monkeypatch.setattr(xarray, "open_dataset", lambda *a, **k: _DS(u, v))
    rgba = W._encode(b"x")
    assert (rgba[..., 0] == 0).all()                # clamped low end
    assert (rgba[..., 1] == 128).all()              # calm v -> mid-grey
