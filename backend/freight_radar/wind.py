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


# forecast hours we publish so the wind can be scrubbed forward: now -> +4 days (daily).
FHOURS = (0, 24, 48, 72, 96)


def _cycle_url(d: date, hh: int, fhour: int = 0) -> str:
    ymd = d.strftime("%Y%m%d")
    return (f"{NOMADS}?dir=%2Fgfs.{ymd}%2F{hh:02d}%2Fatmos"
            f"&file=gfs.t{hh:02d}z.pgrb2.0p25.f{fhour:03d}"
            f"&var_UGRD=on&var_VGRD=on&lev_10_m_above_ground=on")


# Retry only transient TRANSPORT errors (connect/timeout) — NOMADS 503s under load.
# A 404 (cycle not published yet) is NOT an error here; we just try the next cycle.
@retry(reraise=True, stop=stop_after_attempt(3),
       wait=wait_exponential(multiplier=0.5, max=8),
       retry=retry_if_exception_type(httpx.TransportError))
def _get(client: httpx.Client, url: str) -> httpx.Response:
    return client.get(url, timeout=90)


def _fetch(client: httpx.Client, d: date, hh: int, fhour: int) -> bytes | None:
    """One GFS forecast-hour GRIB, or None if it isn't published / isn't valid GRIB."""
    try:
        r = _get(client, _cycle_url(d, hh, fhour))
    except httpx.HTTPError:
        return None
    if r.status_code == 200 and len(r.content) > 50_000 and r.content[:4] == b"GRIB":
        return r.content
    return None


def _latest_cycle(client: httpx.Client) -> tuple[date, int]:
    """Newest GFS cycle whose f000 is published — loop newest->oldest until found."""
    now = datetime.now(timezone.utc)
    for back in range(0, 3):  # today, yesterday, day before
        d = (now - timedelta(days=back)).date()
        for hh in (18, 12, 6, 0):
            if back == 0 and hh > now.hour:
                continue  # cycle hasn't run yet today
            if _fetch(client, d, hh, 0) is not None:
                return d, hh
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
    frames: list[dict] = []
    w = h = 0
    try:
        with httpx.Client(headers={"User-Agent": BROWSER_UA}, follow_redirects=True) as c:
            d, hh = _latest_cycle(c)
            cycle_dt = datetime(d.year, d.month, d.day, hh, tzinfo=timezone.utc)
            for fhour in FHOURS:
                grib = _fetch(c, d, hh, fhour)
                if grib is None:
                    continue  # this forecast hour isn't published yet — skip it
                rgba = _encode(grib)
                h, w = rgba.shape[:2]
                name = f"wind_f{fhour:03d}.png"
                Image.fromarray(rgba, "RGBA").save(out / name, optimize=True)
                valid = cycle_dt + timedelta(hours=fhour)
                frames.append({"fhour": fhour, "valid": valid.strftime("%Y-%m-%d %H:%MZ"),
                               "image": name})
    except Exception as exc:  # noqa: BLE001 - degrade: no wind layer this run
        log.warning("wind layer unavailable this run: %r", exc)
        return {"name": "wind", "sidecar": "wind.json", "error": repr(exc)}
    if not frames:
        return {"name": "wind", "sidecar": "wind.json", "error": "no forecast frames published"}

    cycle = f"{d.isoformat()} {hh:02d}z"
    (out / "wind.json").write_text(json.dumps({
        "generated_at": ctx.today,
        "as_of": ctx.as_of or date.today().isoformat(),
        "source": "NOAA GFS 0.25° 10 m wind (NOMADS)",
        "cycle": cycle,
        "image": frames[0]["image"],   # backward-compat: the f000 analysis frame
        "frames": frames,              # the forecast hours, scrubbable in the UI
        "width": w, "height": h,
        "imageUnscale": list(UNSCALE),
        "bounds": [-180, -90, 180, 90],
    }, separators=(",", ":")))
    return {"name": "wind", "sidecar": "wind.json", "cycle": cycle, "frames": len(frames),
            "size": f"{w}x{h}"}


if __name__ == "__main__":
    import types

    configure_logging()
    from .config import publish_dir

    ctx = types.SimpleNamespace(out_dir=publish_dir(), as_of=date.today().isoformat(),
                                today=date.today().isoformat())
    print(run(ctx))
