"""Ambient global wind layer (10m GFS) -> wind.png + wind.json for the particle layer.

Makes weather visible EVERYWHERE on the globe (not just at storms). Fetches only the
10m UGRD/VGRD pair from NOAA GFS 0.25deg via the NOMADS grib-filter (free, keyless,
~2 MB), decodes with cfgrib/xarray, re-centres longitude to [-180,180], downsamples,
and encodes u->R, v->G into an RGBA PNG (calm wind ~ mid-grey). The weatherlayers-gl
ParticleLayer animates particles along this field on the frontend.

Honest: a weekly nowcast (f000 analysis), labelled "NOAA GFS 10m wind, updated weekly";
degrades to no layer on any failure (the frontend hides it when wind.json is absent).
Source: NOAA GFS — US-government public domain. Free, keyless.
"""

from __future__ import annotations

import json
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import numpy as np
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from ._log import configure as configure_logging
from ._log import get_logger

log = get_logger(__name__)

NOMADS = "https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl"
UNSCALE = (-30.0, 30.0)   # m/s range mapped onto 0..255 per channel (calm -> ~128)
DOWNSAMPLE = 2            # 1440x721 -> 720x361 (lighter ~PNG, plenty for particles)
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


def _cycle_url(d: date, hh: int) -> str:
    ymd = d.strftime("%Y%m%d")
    return (f"{NOMADS}?dir=%2Fgfs.{ymd}%2F{hh:02d}%2Fatmos"
            f"&file=gfs.t{hh:02d}z.pgrb2.0p25.f000"
            f"&var_UGRD=on&var_VGRD=on&lev_10_m_above_ground=on")


# Retry only transient TRANSPORT errors (connect/timeout) — NOMADS 503s under load.
# A 404 (cycle not published yet) is NOT an error here; we just try the next cycle.
@retry(reraise=True, stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=0.5, max=8),
       retry=retry_if_exception_type(httpx.TransportError))
def _get(client: httpx.Client, url: str) -> httpx.Response:
    return client.get(url, timeout=90)


def _latest_grib(client: httpx.Client) -> tuple[bytes, str]:
    """Newest available GFS cycle's 10m u/v GRIB — loop newest->oldest until a 200."""
    now = datetime.now(timezone.utc)
    for back in range(0, 3):  # today, yesterday, day before
        d = (now - timedelta(days=back)).date()
        for hh in (18, 12, 6, 0):
            if back == 0 and hh > now.hour:
                continue  # cycle hasn't run yet today
            try:
                r = _get(client, _cycle_url(d, hh))
            except httpx.HTTPError:
                continue
            if r.status_code == 200 and len(r.content) > 50_000 and r.content[:4] == b"GRIB":
                return r.content, f"{d.isoformat()} {hh:02d}z f000"
    raise RuntimeError("no available GFS cycle found")


def _encode(grib: bytes) -> np.ndarray:
    """GRIB2 (UGRD/VGRD 10m) -> equirectangular RGBA (R=u, G=v), -180..180 / +90..-90."""
    import xarray as xr

    with tempfile.NamedTemporaryFile(suffix=".grib2", delete=False) as tf:
        tf.write(grib)
        path = tf.name
    try:
        ds = xr.open_dataset(
            path, engine="cfgrib",
            backend_kwargs={"indexpath": "",
                            "filter_by_keys": {"typeOfLevel": "heightAboveGround", "level": 10}},
        )
        u = np.asarray(ds["u10"].values, dtype="float32")
        v = np.asarray(ds["v10"].values, dtype="float32")
    finally:
        Path(path).unlink(missing_ok=True)

    half = u.shape[1] // 2                # lon 0..360 -> -180..180
    u = np.roll(u, half, axis=1)
    v = np.roll(v, half, axis=1)
    if DOWNSAMPLE > 1:
        u = u[::DOWNSAMPLE, ::DOWNSAMPLE]
        v = v[::DOWNSAMPLE, ::DOWNSAMPLE]

    lo, hi = UNSCALE

    def enc(a: np.ndarray) -> np.ndarray:
        return np.clip(np.round((np.clip(a, lo, hi) - lo) / (hi - lo) * 255), 0, 255).astype("uint8")

    h, w = u.shape
    rgba = np.zeros((h, w, 4), "uint8")
    rgba[..., 0] = enc(u)
    rgba[..., 1] = enc(v)
    rgba[..., 3] = 255
    return rgba


def run(ctx) -> dict:
    from PIL import Image

    out = Path(ctx.out_dir)
    try:
        with httpx.Client(headers={"User-Agent": BROWSER_UA}, follow_redirects=True) as c:
            grib, cycle = _latest_grib(c)
        rgba = _encode(grib)
    except Exception as exc:  # noqa: BLE001 - degrade: no wind layer this run
        log.warning("wind layer unavailable this run: %r", exc)
        return {"name": "wind", "sidecar": "wind.json", "error": repr(exc)}

    h, w = rgba.shape[:2]
    Image.fromarray(rgba, "RGBA").save(out / "wind.png", optimize=True)
    (out / "wind.json").write_text(json.dumps({
        "generated_at": ctx.today,
        "as_of": ctx.as_of or date.today().isoformat(),
        "source": "NOAA GFS 0.25° 10 m wind (NOMADS)",
        "cycle": cycle,
        "image": "wind.png",
        "width": w, "height": h,
        "imageUnscale": list(UNSCALE),
        "bounds": [-180, -90, 180, 90],
    }, separators=(",", ":")))
    return {"name": "wind", "sidecar": "wind.json", "cycle": cycle, "size": f"{w}x{h}",
            "png_kb": round((out / "wind.png").stat().st_size / 1024, 1)}


if __name__ == "__main__":
    import types

    configure_logging()
    from .config import publish_dir

    ctx = types.SimpleNamespace(out_dir=publish_dir(), as_of=date.today().isoformat(),
                                today=date.today().isoformat())
    print(run(ctx))
