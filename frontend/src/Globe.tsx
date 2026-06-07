import { useEffect, useRef } from 'react';
import type { MutableRefObject } from 'react';
import maplibregl from 'maplibre-gl';
import type { StyleSpecification } from 'maplibre-gl';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { ScatterplotLayer, ArcLayer } from '@deck.gl/layers';
import {
  AMBER,
  PORT,
  LANE,
  QUAKE,
  EVENT,
  WAVE,
  TIDE,
  RIVER,
  severityColor,
  newsCategoryColor,
} from './lib/colors.ts';
import { loadWind, makeWindLayer } from './lib/windLayer.ts';
import type { WindData } from './lib/windLayer.ts';
import type {
  SnapshotPort,
  Lane,
  Vessel,
  Storm,
  Ships,
  NewsGeoItem,
  QuakeItem,
  EonetItem,
  MarineItem,
  TideItem,
  StreamflowItem,
  MapApi,
  GlobeSnapshot,
  GlobeChokepoint,
  GlobeFlag,
  LayerVisibility,
} from './types.ts';

// deck.gl wants fixed-length RGBA tuples; our color constants are 3-element, so append
// the alpha into a real 4-tuple (a `[...c, a]` spread would widen back to number[]).
type RGBA = [number, number, number, number];
const rgba = (c: readonly number[], a: number): RGBA => [c[0], c[1], c[2], a];

// deck.gl v9 (luma.gl v9) GPU depth parameters for the flat, screen-space marker discs.
// THE blink fix: in interleaved mode deck shares MapLibre's depth buffer, but the v5 globe
// writes its sphere surface with its OWN depth formula (it "calculates z in the vertex
// shader") while deck depth-tests these dots with a perspective near/far from the map
// transform. The two encodings disagree at the same screen pixel, so a dot's depth
// straddles the surface and intermittently fails deck's default `depthCompare:'less-equal'`
// — it drops behind the globe and pops back, i.e. blinks, and worsens as zoom collapses
// near-surface depth precision. These dots are 2-D pixel billboards with no real
// globe-surface depth, so the correct fix is to take them out of the depth test entirely:
// always pass, never write. (v9 removed the old `depthTest:false` boolean; these are the
// replacement keys.) The 3-D great-circle ArcLayer is intentionally left depth-tested so
// back-of-globe lanes stay hidden.
const MARKER_PARAMETERS = { depthCompare: 'always', depthWriteEnabled: false } as const;

// NASA GIBS VIIRS true-color is published ~a day behind; use 2 days back to be safe.
// Computed at load, so the satellite layer is always recent + the date is honestly shown.
export const GIBS_DATE = (() => {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 2);
  return d.toISOString().slice(0, 10);
})();

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
    // real near-real-time satellite imagery (free, keyless) — actual cloud systems +
    // storms over the chokepoints. Off by default (it changes the light aesthetic);
    // toggled from the layer panel. WMTS REST is {z}/{y}/{x} (TileRow before TileCol).
    gibs: {
      type: 'raster',
      tiles: [
        `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/VIIRS_SNPP_CorrectedReflectance_TrueColor/default/${GIBS_DATE}/GoogleMapsCompatible_Level9/{z}/{y}/{x}.jpg`,
      ],
      tileSize: 256,
      maxzoom: 9,
      attribution: 'Satellite: NASA EOSDIS GIBS · VIIRS',
    },
  },
  layers: [
    { id: 'space', type: 'background', paint: { 'background-color': '#dfe5ee' } },
    // fully opaque basemap so the globe reads as a solid sphere (not washed-out)
    { id: 'carto', type: 'raster', source: 'carto', paint: { 'raster-opacity': 1 } },
    // real satellite imagery, above the basemap, hidden until toggled on
    {
      id: 'gibs-satellite',
      type: 'raster',
      source: 'gibs',
      layout: { visibility: 'none' },
      paint: { 'raster-opacity': 1 },
    },
  ],
  sky: {
    'sky-color': '#cfddf0',
    'sky-horizon-blend': 0.4,
    'horizon-color': '#eef2f7',
    'horizon-fog-blend': 0.7,
    'fog-color': '#eef2f7',
    // push fog to the far horizon only (high blend) so the surface stays crisp, not hazy
    'fog-ground-blend': 0.9,
    'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 0.35, 5, 0.12, 8, 0.0],
  },
};

const sqrtScale = (v: number, k: number): number => Math.sqrt(Math.max(0, v)) * k;

// live AIS vessel dot color by coarse type (AIS only resolves cargo/tanker/etc.).
// Vivid, higher-chroma so the live ships read clearly against the muted slate ports;
// generic vessels are bright teal (the majority of an AIS sample).
const VESSEL_COLOR: Record<string, [number, number, number]> = {
  cargo: [37, 99, 235], // bright blue
  tanker: [234, 88, 12], // bright orange
  passenger: [147, 51, 234], // violet
  fishing: [202, 138, 4], // gold
  vessel: [13, 184, 156], // bright teal
};

interface LayerInputs {
  ports: SnapshotPort[];
  chokepoints: GlobeChokepoint[];
  lanes: Lane[];
  flags: GlobeFlag[];
  ships: Vessel[];
  storms: Storm[];
  newsDots: NewsGeoItem[];
  quakeDots: QuakeItem[];
  eonetDots: EonetItem[];
  marineDots: MarineItem[];
  tideDots: TideItem[];
  streamDots: StreamflowItem[];
  selectedId: string | null;
  onSelectFlag: (flag: GlobeFlag) => void;
  layers: LayerVisibility;
  highlightIds: string[];
}

// a vivid cyan, used ONLY for the search/hover highlight ring so it never reads as data
const HIGHLIGHT: readonly number[] = [6, 182, 212];

function buildLayers({
  ports,
  chokepoints,
  lanes,
  flags,
  ships,
  storms,
  newsDots,
  quakeDots,
  eonetDots,
  marineDots,
  tideDots,
  streamDots,
  selectedId,
  onSelectFlag,
  layers,
  highlightIds,
}: LayerInputs) {
  // resolve the highlighted portids (from row-hover / search) to positions
  const posOf = new Map<string, [number, number]>();
  chokepoints.forEach((c) => posOf.set(c.portid, [c.lon, c.lat]));
  ports.forEach((p) => posOf.set(p.portid, [p.lon, p.lat]));
  const hits = highlightIds.map((id) => posOf.get(id)).filter(Boolean) as [number, number][];
  return [
    // shipping lanes — thin, soft great-circle arcs
    new ArcLayer({
      id: 'lanes',
      visible: layers.lanes,
      data: lanes,
      getSourcePosition: (d) => d.from,
      getTargetPosition: (d) => d.to,
      getSourceColor: rgba(LANE, 18),
      getTargetColor: rgba(LANE, 70),
      getWidth: (d) => 0.5 + d.intensity * 1.4,
      greatCircle: true,
    }),

    // ports — solid slate dots. A FIXED screen size (equal min/max radius) means each
    // dot never resizes or sub-pixel-jitters as you zoom — it stays exactly where it is.
    // Full opacity + a faint white edge gives it a hard boundary so it reads as fully
    // "there" instead of shimmering dust.
    new ScatterplotLayer({
      id: 'ports',
      visible: layers.ports,
      parameters: MARKER_PARAMETERS,
      data: ports,
      getPosition: (d) => [d.lon, d.lat],
      // size by annual vessel traffic so the map reads as a hierarchy (big ports first),
      // not undifferentiated dust — still pixel-fixed per dot, so no zoom shimmer.
      getRadius: (d) => 1.5 + sqrtScale(d.vessels, 0.045),
      radiusUnits: 'pixels',
      radiusMinPixels: 1.5,
      radiusMaxPixels: 5,
      getFillColor: rgba(PORT, 255),
      stroked: true,
      getLineColor: rgba([255, 255, 255], 130),
      lineWidthMinPixels: 0.6,
      pickable: true,
    }),

    // GDELT world-news dots — one real geo-located article per dot, coloured by topic.
    // CONTEXT, not freight: small, semi-transparent, drawn BELOW the freight marks so the
    // measured layer always reads on top. Clicking a dot opens its cited source article.
    new ScatterplotLayer({
      id: 'news',
      visible: layers.news,
      parameters: MARKER_PARAMETERS,
      data: newsDots,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 3.4,
      radiusUnits: 'pixels',
      radiusMinPixels: 3.4,
      radiusMaxPixels: 3.4,
      getFillColor: (d) => rgba(newsCategoryColor(d.category), 200),
      stroked: true,
      getLineColor: rgba([255, 255, 255], 150),
      lineWidthMinPixels: 0.5,
      pickable: true,
      onClick: (info) => {
        const url = (info.object as NewsGeoItem | undefined)?.url;
        if (url) window.open(url, '_blank', 'noopener,noreferrer');
      },
      updateTriggers: { getFillColor: newsDots },
    }),

    // USGS earthquakes (M4+, past 7 days) — terracotta dots SIZED BY MAGNITUDE so a M7
    // reads bigger than a M4. CONTEXT, below the freight marks; click opens the USGS
    // event page. A co-located physical fact, never a stated cause.
    new ScatterplotLayer({
      id: 'quakes',
      visible: layers.quakes,
      parameters: MARKER_PARAMETERS,
      data: quakeDots,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => 2 + Math.max(0, d.mag - 4) * 1.5,
      radiusUnits: 'pixels',
      radiusMinPixels: 2,
      radiusMaxPixels: 9,
      getFillColor: rgba(QUAKE, 190),
      stroked: true,
      getLineColor: rgba([255, 255, 255], 150),
      lineWidthMinPixels: 0.5,
      pickable: true,
      onClick: (info) => {
        const url = (info.object as QuakeItem | undefined)?.url;
        if (url) window.open(url, '_blank', 'noopener,noreferrer');
      },
    }),

    // NASA EONET natural events (wildfires, volcanoes, severe storms, ice) — burnt-orange
    // dots. CONTEXT, below the freight marks; click opens the source. A co-located fact.
    new ScatterplotLayer({
      id: 'eonet',
      visible: layers.eonet,
      parameters: MARKER_PARAMETERS,
      data: eonetDots,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 3,
      radiusUnits: 'pixels',
      radiusMinPixels: 2,
      radiusMaxPixels: 6,
      getFillColor: rgba(EVENT, 180),
      stroked: true,
      getLineColor: rgba([255, 255, 255], 140),
      lineWidthMinPixels: 0.5,
      pickable: true,
      onClick: (info) => {
        const url = (info.object as EonetItem | undefined)?.url;
        if (url) window.open(url, '_blank', 'noopener,noreferrer');
      },
    }),

    // Open-Meteo marine wave height at the chokepoints — steel-blue dots SIZED BY wave
    // height. CONTEXT, below the freight marks; the sea-state backdrop, association-only.
    new ScatterplotLayer({
      id: 'marine',
      visible: layers.marine,
      parameters: MARKER_PARAMETERS,
      data: marineDots,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => 2 + Math.max(0, d.wave_height_m) * 1.6,
      radiusUnits: 'pixels',
      radiusMinPixels: 2,
      radiusMaxPixels: 10,
      getFillColor: rgba(WAVE, 170),
      stroked: true,
      getLineColor: rgba([255, 255, 255], 130),
      lineWidthMinPixels: 0.5,
    }),

    // NOAA CO-OPS observed water level at major US ports — teal dots. CONTEXT: a cited
    // tide reading the reader weighs (tides set draft windows); association-only, never a cause.
    new ScatterplotLayer({
      id: 'tides',
      visible: layers.tides,
      parameters: MARKER_PARAMETERS,
      data: tideDots,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 5,
      radiusUnits: 'pixels',
      radiusMinPixels: 3,
      radiusMaxPixels: 8,
      getFillColor: rgba(TIDE, 175),
      stroked: true,
      getLineColor: rgba([255, 255, 255], 130),
      lineWidthMinPixels: 0.5,
      pickable: true,
      onClick: (info) => {
        const url = (info.object as TideItem | undefined)?.url;
        if (url) window.open(url, '_blank', 'noopener');
      },
    }),

    // USGS observed river stage at inland freight gauges (Mississippi etc.) — river-green
    // dots. CONTEXT: a cited stage reading the reader weighs (low water narrows barge
    // drafts); association-only, never a stated cause.
    new ScatterplotLayer({
      id: 'streamflow',
      visible: layers.streamflow,
      parameters: MARKER_PARAMETERS,
      data: streamDots,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 5,
      radiusUnits: 'pixels',
      radiusMinPixels: 3,
      radiusMaxPixels: 8,
      getFillColor: rgba(RIVER, 175),
      stroked: true,
      getLineColor: rgba([255, 255, 255], 130),
      lineWidthMinPixels: 0.5,
      pickable: true,
      onClick: (info) => {
        const url = (info.object as StreamflowItem | undefined)?.url;
        if (url) window.open(url, '_blank', 'noopener');
      },
    }),

    // live AIS vessels — REAL current positions near the chokepoints (a sample). A soft
    // type-colored glow makes each one read as a live point that stands out from the
    // static slate ports, even when zoomed out where they cluster at the chokepoints…
    new ScatterplotLayer({
      id: 'ships-glow',
      visible: layers.ships,
      parameters: MARKER_PARAMETERS,
      data: ships || [],
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 8.5,
      radiusUnits: 'pixels',
      radiusMinPixels: 8.5,
      radiusMaxPixels: 8.5,
      getFillColor: (d) => rgba(VESSEL_COLOR[d.type] || VESSEL_COLOR.vessel, 64),
    }),

    // chokepoints — solid amber circles with a clean white ring
    new ScatterplotLayer({
      id: 'choke',
      visible: layers.chokepoints,
      parameters: MARKER_PARAMETERS,
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

    // the bright AIS ship cores draw ON TOP of the amber chokepoints (their soft glow sits
    // UNDER the chokepoints above, so the chokepoints stay readable) — bigger + brighter so
    // vessels read as live points, not port dust. Type-colored with a white edge.
    new ScatterplotLayer({
      id: 'ships',
      visible: layers.ships,
      parameters: MARKER_PARAMETERS,
      data: ships || [],
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 4.5,
      radiusUnits: 'pixels',
      radiusMinPixels: 4.5,
      radiusMaxPixels: 4.5,
      getFillColor: (d) => rgba(VESSEL_COLOR[d.type] || VESSEL_COLOR.vessel, 255),
      stroked: true,
      getLineColor: rgba([255, 255, 255], 230),
      lineWidthMinPixels: 1,
      pickable: true,
    }),

    // active tropical cyclones (live NHC + GDACS) — a storm-blue halo SIZED BY
    // intensity (stronger storm = bigger glow) + a crisp core dot on position. The
    // halo alpha is high enough to read clearly as weather against the ocean.
    new ScatterplotLayer({
      id: 'storms-halo',
      visible: layers.storms,
      parameters: MARKER_PARAMETERS,
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
      visible: layers.storms,
      parameters: MARKER_PARAMETERS,
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
      visible: layers.flags,
      parameters: MARKER_PARAMETERS,
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
      visible: layers.flags,
      parameters: MARKER_PARAMETERS,
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

    // search / hover highlight — a vivid cyan ring over the matched entities, on top of
    // everything, so "highlight different things" + "search for different things" land
    // visibly on the globe. Pixel-fixed + depth-out (MARKER_PARAMETERS) like the markers.
    new ScatterplotLayer({
      id: 'highlight',
      visible: hits.length > 0,
      parameters: MARKER_PARAMETERS,
      data: hits,
      getPosition: (d) => d,
      getRadius: 9,
      radiusUnits: 'pixels',
      radiusMinPixels: 9,
      radiusMaxPixels: 9,
      filled: false,
      stroked: true,
      getLineColor: rgba(HIGHLIGHT, 255),
      lineWidthUnits: 'pixels',
      getLineWidth: 2.5,
    }),
  ];
}

interface GlobeProps {
  snapshot: GlobeSnapshot | null;
  lanes: Lane[];
  flags: GlobeFlag[];
  ships: Ships | null;
  storms: Storm[] | undefined;
  newsDots: NewsGeoItem[];
  quakeDots: QuakeItem[];
  eonetDots: EonetItem[];
  marineDots: MarineItem[];
  tideDots: TideItem[];
  streamDots: StreamflowItem[];
  selectedFlag: GlobeFlag | null;
  onSelectFlag: (flag: GlobeFlag) => void;
  mapApiRef: MutableRefObject<MapApi | null>;
  windOn: boolean;
  windFrame: number;
  layers: LayerVisibility;
  highlightIds: string[];
}

export default function Globe({
  snapshot,
  lanes,
  flags,
  ships,
  storms,
  newsDots,
  quakeDots,
  eonetDots,
  marineDots,
  tideDots,
  streamDots,
  selectedFlag,
  onSelectFlag,
  mapApiRef,
  windOn,
  windFrame,
  layers,
  highlightIds,
}: GlobeProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const windOverlayRef = useRef<MapboxOverlay | null>(null);
  const windDataRef = useRef<WindData | null>(null);
  // read the live toggle inside the async wind load without re-running the mount effect
  const windOnRef = useRef(windOn);
  windOnRef.current = windOn;
  const windFrameRef = useRef(windFrame);
  windFrameRef.current = windFrame;

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
        if (layer?.id === 'news') {
          // a cited, geo-tagged article — a possibly-related signal near a place, not a
          // stated cause. Click opens the source.
          return {
            html:
              `<b>${object.category_label}</b> · ${object.place}<br/>` +
              `${object.domain} · ${object.seen}<br/><span class="fr-tip-cta">click to read · GDELT</span>`,
            className: 'fr-tip',
          };
        }
        if (layer?.id === 'quakes') {
          // an observed seismic event the reader can weigh — never a stated cause.
          const ts = object.tsunami ? ' · 🌊 tsunami flag' : '';
          const dep = object.depth_km != null ? ` · ${object.depth_km} km deep` : '';
          return {
            html:
              `<b>M${object.mag.toFixed(1)} earthquake</b> · ${object.place}<br/>` +
              `${object.time}${dep}${ts}<br/><span class="fr-tip-cta">click for USGS event</span>`,
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
    windOverlayRef.current = windOverlay;
    map.addControl(windOverlay);
    let windCancelled = false;
    loadWind(import.meta.env.BASE_URL || '/')
      .then((wd) => {
        if (!wd || windCancelled) return;
        windDataRef.current = wd;
        // honour the current toggle + forecast frame when the data finishes loading
        const i = Math.min(windFrameRef.current, wd.frames.length - 1);
        windOverlay.setProps({
          layers: windOnRef.current ? [makeWindLayer(wd.frames[i].image, wd.meta)] : [],
        });
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
      windOverlayRef.current = null;
      windDataRef.current = null;
      map.remove();
    };
  }, [mapApiRef]);

  // Show/hide the wind when the toggle flips, and swap to the chosen forecast frame when the
  // scrubber moves. Each change builds a FRESH ParticleLayer (deck can't re-add a finalized
  // one); disabling drops it entirely.
  useEffect(() => {
    const overlay = windOverlayRef.current;
    const wd = windDataRef.current;
    if (!overlay) return;
    const i = wd ? Math.min(windFrame, wd.frames.length - 1) : 0;
    overlay.setProps({
      layers: windOn && wd ? [makeWindLayer(wd.frames[i].image, wd.meta)] : [],
    });
  }, [windOn, windFrame]);

  // show/hide the NASA satellite raster (a maplibre layer, not a deck layer) from the panel
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      if (map.getLayer('gibs-satellite')) {
        const vis = layers.satellite ? 'visible' : 'none';
        map.setLayoutProperty('gibs-satellite', 'visibility', vis);
      }
    };
    if (map.isStyleLoaded()) apply();
    else map.once('load', apply);
  }, [layers.satellite]);

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
        newsDots: newsDots ?? [], // GDELT geo-tagged world-news (context)
        quakeDots: quakeDots ?? [], // USGS M4+ earthquakes (context)
        eonetDots: eonetDots ?? [], // NASA EONET natural events (context)
        marineDots: marineDots ?? [], // Open-Meteo wave height at chokepoints (context)
        tideDots: tideDots ?? [], // NOAA CO-OPS water level at US ports (context)
        streamDots: streamDots ?? [], // USGS river stage at inland gauges (context)
        flags: flags ?? [],
        selectedId: selectedFlag?.flag_id ?? null,
        onSelectFlag,
        layers,
        highlightIds,
      }),
    });
  }, [
    snapshot,
    lanes,
    flags,
    ships,
    storms,
    newsDots,
    eonetDots,
    marineDots,
    tideDots,
    streamDots,
    quakeDots,
    selectedFlag,
    onSelectFlag,
    layers,
    highlightIds,
  ]);

  return (
    <div
      ref={containerRef}
      className="fr-globe"
      role="img"
      aria-label="Globe showing ocean-freight chokepoints, ports, sampled live vessel positions, active storms, animated wind and geo-tagged world-news coverage"
    />
  );
}
