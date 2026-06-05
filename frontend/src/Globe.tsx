import { useEffect, useRef } from 'react';
import type { MutableRefObject } from 'react';
import maplibregl from 'maplibre-gl';
import type { StyleSpecification } from 'maplibre-gl';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { ScatterplotLayer, ArcLayer } from '@deck.gl/layers';
import { AMBER, PORT, LANE, severityColor } from './lib/colors.ts';
import { makeWindLayer } from './lib/windLayer.ts';
import type {
  SnapshotPort,
  Lane,
  Vessel,
  Storm,
  Ships,
  MapApi,
  GlobeSnapshot,
  GlobeChokepoint,
  GlobeFlag,
} from './types.ts';

// deck.gl wants fixed-length RGBA tuples; our color constants are 3-element, so append
// the alpha into a real 4-tuple (a `[...c, a]` spread would widen back to number[]).
type RGBA = [number, number, number, number];
const rgba = (c: readonly number[], a: number): RGBA => [c[0], c[1], c[2], a];

// Clean, token-free LIGHT basemap (CARTO Positron) draped on the v5 globe.
// 'light_nolabels' @2x drops the busy place labels + boundary clutter and serves
// retina (512px) tiles, so the whole map reads sharp at every zoom.
const STYLE: StyleSpecification = {
  version: 8,
  projection: { type: 'globe' },
  sources: {
    carto: {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}@2x.png',
        'https://b.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}@2x.png',
        'https://c.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}@2x.png',
        'https://d.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}@2x.png',
      ],
      tileSize: 512,
      attribution: '© OpenStreetMap © CARTO · Wind: NOAA GFS',
    },
  },
  layers: [
    { id: 'space', type: 'background', paint: { 'background-color': '#e9edf3' } },
    { id: 'carto', type: 'raster', source: 'carto', paint: { 'raster-opacity': 0.94 } },
  ],
  sky: {
    'sky-color': '#d6e3f4',
    'sky-horizon-blend': 0.5,
    'horizon-color': '#eef2f7',
    'horizon-fog-blend': 0.6,
    'fog-color': '#eef2f7',
    'fog-ground-blend': 0.5,
    'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 0.5, 5, 0.2, 8, 0.0],
  },
};

const sqrtScale = (v: number, k: number): number => Math.sqrt(Math.max(0, v)) * k;

// live AIS vessel dot color by coarse type (AIS only resolves cargo/tanker/etc.).
// Generic vessels use teal so they read as ships, distinct from the slate port dust.
const VESSEL_COLOR: Record<string, [number, number, number]> = {
  cargo: [58, 110, 165],
  tanker: [194, 97, 31],
  passenger: [120, 106, 154],
  fishing: [138, 109, 59],
  vessel: [13, 148, 136],
};

interface LayerInputs {
  ports: SnapshotPort[];
  chokepoints: GlobeChokepoint[];
  lanes: Lane[];
  flags: GlobeFlag[];
  ships: Vessel[];
  storms: Storm[];
  selectedId: string | null;
  onSelectFlag: (flag: GlobeFlag) => void;
}

function buildLayers({
  ports,
  chokepoints,
  lanes,
  flags,
  ships,
  storms,
  selectedId,
  onSelectFlag,
}: LayerInputs) {
  return [
    // shipping lanes — thin, soft great-circle arcs
    new ArcLayer({
      id: 'lanes',
      data: lanes,
      getSourcePosition: (d) => d.from,
      getTargetPosition: (d) => d.to,
      getSourceColor: rgba(LANE, 18),
      getTargetColor: rgba(LANE, 70),
      getWidth: (d) => 0.5 + d.intensity * 1.4,
      greatCircle: true,
    }),

    // ports — faint dark dust (no glow); clean pinpricks on the light globe.
    // A near-fixed 2–2.5px dot (never sub-pixel) stops the shimmer/flicker on ~2000
    // points while panning/zooming; alpha 200 keeps each dot a solid, crisp pinprick.
    new ScatterplotLayer({
      id: 'ports',
      data: ports,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => sqrtScale(d.vessels, 0.34),
      radiusUnits: 'pixels',
      radiusMinPixels: 2,
      radiusMaxPixels: 2.6,
      getFillColor: rgba(PORT, 200),
      pickable: true,
    }),

    // live AIS vessels — REAL current positions near the chokepoints (a sample), as
    // crisp little type-colored dots with a thin white edge. Clear "where ships are",
    // not the old confusing animated streaks.
    new ScatterplotLayer({
      id: 'ships',
      data: ships || [],
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 2.4,
      radiusUnits: 'pixels',
      radiusMinPixels: 2,
      radiusMaxPixels: 3.2,
      getFillColor: (d) => VESSEL_COLOR[d.type] || VESSEL_COLOR.vessel,
      stroked: true,
      getLineColor: rgba([255, 255, 255], 170),
      lineWidthMinPixels: 0.5,
      pickable: true,
    }),

    // chokepoints — solid amber circles with a clean white ring
    new ScatterplotLayer({
      id: 'choke',
      data: chokepoints,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => 2.8 + sqrtScale(d.n_total, 0.24),
      radiusUnits: 'pixels',
      radiusMinPixels: 3,
      radiusMaxPixels: 8.5,
      getFillColor: rgba(AMBER, 255),
      stroked: true,
      lineWidthMinPixels: 1.4,
      getLineColor: rgba([255, 255, 255], 235),
      pickable: true,
    }),

    // active tropical cyclones (live NHC + GDACS) — a storm-blue halo SIZED BY
    // intensity (stronger storm = bigger glow) + a crisp core dot on position. The
    // halo alpha is high enough to read clearly as weather against the ocean.
    new ScatterplotLayer({
      id: 'storms-halo',
      data: storms || [],
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => 13 + Math.min((d.max_wind_kmh || 0) / 8, 22),
      radiusUnits: 'pixels',
      radiusMinPixels: 13,
      radiusMaxPixels: 36,
      filled: true,
      stroked: true,
      getFillColor: rgba([47, 93, 153], 70),
      getLineColor: rgba([47, 93, 153], 120),
      lineWidthMinPixels: 1,
    }),
    new ScatterplotLayer({
      id: 'storms',
      data: storms || [],
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 1,
      radiusUnits: 'pixels',
      radiusMinPixels: 5,
      radiusMaxPixels: 5,
      filled: true,
      stroked: true,
      getFillColor: rgba([47, 93, 153], 235),
      getLineColor: rgba([255, 255, 255], 240),
      lineWidthMinPixels: 1.6,
      pickable: true,
    }),

    // flags — a soft static severity-tinted glow + a crisp filled core with a white
    // ring, centered exactly on the entity. No animation, no expanding ring: the
    // marker is rock-steady at every zoom and reads its position precisely.
    new ScatterplotLayer({
      id: 'flags-halo',
      data: flags,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 1,
      radiusUnits: 'pixels',
      radiusMinPixels: 15,
      radiusMaxPixels: 15,
      filled: true,
      stroked: false,
      getFillColor: (d) => severityColor(d.severity, 34),
    }),
    new ScatterplotLayer({
      id: 'flags-ring',
      data: flags,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => (d.flag_id === selectedId ? 9 : 7),
      radiusUnits: 'pixels',
      radiusMinPixels: 7,
      radiusMaxPixels: 9,
      filled: true,
      stroked: true,
      getFillColor: (d) => severityColor(d.severity, 255),
      getLineColor: rgba([255, 255, 255], 255),
      lineWidthUnits: 'pixels',
      getLineWidth: (d) => (d.flag_id === selectedId ? 3.2 : 2),
      updateTriggers: { getLineWidth: selectedId, getRadius: selectedId },
      pickable: true,
      onClick: (info) => info.object && onSelectFlag(info.object),
    }),
  ];
}

interface GlobeProps {
  snapshot: GlobeSnapshot | null;
  lanes: Lane[];
  flags: GlobeFlag[];
  ships: Ships | null;
  storms: Storm[] | undefined;
  selectedFlag: GlobeFlag | null;
  onSelectFlag: (flag: GlobeFlag) => void;
  mapApiRef: MutableRefObject<MapApi | null>;
}

export default function Globe({
  snapshot,
  lanes,
  flags,
  ships,
  storms,
  selectedFlag,
  onSelectFlag,
  mapApiRef,
}: GlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);

  // Create the map, the interleaved marker overlay, and the separate self-animating
  // wind overlay exactly once. mapApiRef is the only external value used (a stable ref
  // from the parent), so this honestly runs on mount — no eslint-disable needed.
  useEffect(() => {
    if (!containerRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [70, 20],
      zoom: 1.55,
      minZoom: 0.8,
      maxZoom: 7,
      pitch: 0,
      bearing: 0,
      attributionControl: { compact: true },
      dragRotate: false,
      // MSAA — smooths deck marker edges in interleaved mode (v5 moved this under
      // canvasContextAttributes from the old top-level `antialias`).
      canvasContextAttributes: { antialias: true },
    });
    map.scrollZoom.setWheelZoomRate(1 / 200);
    mapRef.current = map;

    const overlay = new MapboxOverlay({
      interleaved: true,
      pickingRadius: 6, // forgiving hover/click — grab a dot from a few px away
      layers: [],
      getTooltip: ({ object, layer }) => {
        if (!object) return null;
        if (layer?.id?.startsWith('flags')) {
          return { html: `<b>${object.entity}</b><br/>${object.headline}`, className: 'fr-tip' };
        }
        if (layer?.id === 'choke') {
          const pct =
            object.pct_change != null
              ? ` · ${object.pct_change > 0 ? '+' : ''}${object.pct_change}% vs 28d`
              : '';
          return {
            html: `<b>${object.name}</b><br/>${object.n_total} vessels/day${pct}`,
            className: 'fr-tip',
          };
        }
        if (layer?.id === 'ports') {
          return {
            html: `<b>${object.name}</b>${object.country ? ', ' + object.country : ''}<br/>${object.vessels.toLocaleString()} vessels/yr`,
            className: 'fr-tip',
          };
        }
        if (layer?.id === 'storms') {
          const wind = object.max_wind_kmh ? ` · ${object.max_wind_kmh} km/h` : '';
          return {
            html: `🌀 <b>${object.name}</b> (${object.category})<br/>${object.basin}${wind} · live ${object.agency}`,
            className: 'fr-tip',
          };
        }
        if (layer?.id === 'ships') {
          const nm = object.name ? `<b>${object.name}</b>` : `<b>Vessel ${object.mmsi}</b>`;
          return {
            html: `${nm}<br/>${object.type} · heading ${object.heading}° · AIS`,
            className: 'fr-tip',
          };
        }
        return null;
      },
    });
    map.addControl(overlay);
    overlayRef.current = overlay;

    // Animated global wind lives on its OWN overlaid overlay (interleaved:false) so its
    // self-animating particle sim never re-triggers the static marker overlay's
    // !isMoving rebuild gate (and never fights the basemap's per-frame globe redraw).
    // It draws UNDER the markers, which stay on the interleaved overlay above.
    const windOverlay = new MapboxOverlay({ interleaved: false, layers: [] });
    map.addControl(windOverlay);
    let windCancelled = false;
    makeWindLayer(import.meta.env.BASE_URL || '/')
      .then((layer) => {
        if (layer && !windCancelled) windOverlay.setProps({ layers: [layer] });
      })
      .catch(() => {});

    map.on('load', () => map.resize());

    // The globe NEVER moves on its own — no auto-rotate, no idle drift. It only moves
    // when the user drives it, or when a row click flies to an entity (below).
    if (mapApiRef) {
      mapApiRef.current = {
        flyTo: (lon: number, lat: number) =>
          map.flyTo({ center: [lon, lat], zoom: 3.4, duration: 2400, essential: true }),
      };
    }

    return () => {
      windCancelled = true;
      try {
        windOverlay.setProps({ layers: [] });
        map.removeControl(windOverlay);
      } catch {
        /* noop */
      }
      overlayRef.current = null;
      map.remove();
    };
  }, [mapApiRef]);

  // Data/selection-driven layer push: rebuild the deck layers ONLY when the underlying
  // data or the current selection changes — never on a timer. In interleaved mode deck
  // re-renders the existing layer instances in lockstep with the basemap during a
  // pan/zoom on its own, so there is no idle requestAnimationFrame and no mid-gesture
  // re-instantiation (the old marker blink is gone by construction). The wind overlay
  // is independent and self-animates.
  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) return;
    overlay.setProps({
      layers: buildLayers({
        ports: snapshot?.ports ?? [],
        chokepoints: snapshot?.chokepoints ?? [],
        lanes: lanes ?? [],
        ships: ships?.vessels ?? [], // live AIS positions near the chokepoints
        storms: storms ?? [],
        flags: flags ?? [],
        selectedId: selectedFlag?.flag_id ?? null,
        onSelectFlag,
      }),
    });
  }, [snapshot, lanes, flags, ships, storms, selectedFlag, onSelectFlag]);

  return (
    <div
      ref={containerRef}
      className="fr-globe"
      role="img"
      aria-label="Globe showing ocean-freight chokepoints, ports, sampled live vessel positions, active storms and animated wind"
    />
  );
}
