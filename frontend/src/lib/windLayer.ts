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

type Texture = Awaited<ReturnType<typeof loadTextureData>>;

export interface WindFrameData {
  fhour: number;
  valid: string;
  image: Texture;
}
export interface WindData {
  frames: WindFrameData[]; // GFS forecast hours (now -> +N days), scrubbable
  meta: Wind;
}

/** Fetch wind.json + decode every forecast-frame texture. Returns null when wind is absent
 *  (layer hidden, the rest of the globe unaffected). Falls back to the single legacy image. */
export async function loadWind(base = '/'): Promise<WindData | null> {
  let meta: Wind | null;
  try {
    const r = await fetch(`${base}data/wind.json`);
    meta = r.ok ? ((await r.json()) as Wind | null) : null;
  } catch {
    meta = null;
  }
  if (!meta?.image) return null;
  const list = meta.frames?.length
    ? meta.frames
    : [{ fhour: 0, valid: meta.cycle, image: meta.image }];
  const frames: WindFrameData[] = [];
  for (const f of list) {
    try {
      const image = await loadTextureData(`${base}data/${f.image}`);
      frames.push({ fhour: f.fhour, valid: f.valid, image });
    } catch {
      /* skip a frame that fails to decode; the others still scrub */
    }
  }
  if (!frames.length) return null;
  return { frames, meta };
}

/** A fresh ParticleLayer for one forecast frame's texture (call again to re-enable/swap). */
export function makeWindLayer(image: Texture, meta: Wind): ParticleLayer {
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
