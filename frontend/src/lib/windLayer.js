import { ParticleLayer, loadTextureData, ImageType } from 'weatherlayers-gl';

// Animated global wind particles (Phase: ambient weather). Built from the published
// GFS wind PNG (R=u, G=v) — see backend/freight_radar/wind.py. Self-animates via the
// weatherlayers-gl ParticleLayer, so it lives on its OWN overlaid deck overlay (not the
// static interleaved marker overlay). Returns null when wind.json is absent (layer
// simply hidden — the rest of the globe is unaffected). Source: NOAA GFS (public domain).
export async function makeWindLayer(base = '/') {
  let meta;
  try {
    const r = await fetch(`${base}data/wind.json`);
    meta = r.ok ? await r.json() : null;
  } catch {
    meta = null;
  }
  if (!meta?.image) return null;

  const image = await loadTextureData(`${base}data/${meta.image}`);
  return new ParticleLayer({
    id: 'wind',
    image,
    imageType: ImageType.VECTOR,
    imageUnscale: meta.imageUnscale,   // [-30, 30] m/s -> the PNG's 0..255 range
    bounds: meta.bounds,               // [-180, -90, 180, 90]
    numParticles: 3500,
    maxAge: 25,
    speedFactor: 4,
    width: 1.6,
    color: [72, 102, 150],             // soft slate-blue, reads as wind under the markers
    opacity: 0.42,
    animate: true,
  });
}
