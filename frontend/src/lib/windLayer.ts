import { ParticleLayer, loadTextureData, ImageType } from 'weatherlayers-gl';
import type { Wind } from '../types.ts';

// Animated global wind particles (ambient weather). Built from the published GFS wind
// PNG (R=u, G=v) — see backend/freight_radar/wind.py. Self-animates via the
// weatherlayers-gl ParticleLayer, so it lives on its OWN overlaid deck overlay (not the
// static interleaved marker overlay). Source: NOAA GFS (public domain).
//
// Loading (fetch + texture decode) is split from layer creation so the legend toggle can
// drop the layer entirely and rebuild a FRESH instance when re-enabled — a ParticleLayer
// can't be re-added once deck has finalized it.

export interface WindData {
  image: Awaited<ReturnType<typeof loadTextureData>>;
  meta: Wind;
}

/** Fetch wind.json + decode the texture. Returns null when wind is absent (layer hidden,
 *  the rest of the globe unaffected). */
export async function loadWind(base = '/'): Promise<WindData | null> {
  let meta: Wind | null;
  try {
    const r = await fetch(`${base}data/wind.json`);
    meta = r.ok ? ((await r.json()) as Wind | null) : null;
  } catch {
    meta = null;
  }
  if (!meta?.image) return null;
  const image = await loadTextureData(`${base}data/${meta.image}`);
  return { image, meta };
}

/** A fresh ParticleLayer from already-loaded wind data (call again to re-enable). */
export function makeWindLayer({ image, meta }: WindData): ParticleLayer {
  // respect prefers-reduced-motion: render a static field instead of flowing particles
  const reduceMotion =
    typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
  return new ParticleLayer({
    id: 'wind',
    image,
    imageType: ImageType.VECTOR,
    imageUnscale: meta.imageUnscale, // [-30, 30] m/s -> the PNG's 0..255 range
    bounds: meta.bounds, // [-180, -90, 180, 90]
    // tuned to read as a calm ambient field, not a busy storm of streaks: fewer,
    // slower, softer particles (the legend chip toggles the whole layer off).
    numParticles: 1800,
    maxAge: 22,
    speedFactor: 3,
    width: 1.4,
    color: [96, 124, 165], // soft slate-blue, reads as wind under the markers
    opacity: 0.28,
    animate: !reduceMotion,
  });
}
