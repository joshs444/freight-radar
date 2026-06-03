import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { ScatterplotLayer, ArcLayer } from '@deck.gl/layers';
import { AMBER, CYAN, LANE, severityColor } from './lib/colors.js';

// Dark, token-free basemap (CARTO dark-matter raster) draped on the v5 globe.
const STYLE = {
  version: 8,
  projection: { type: 'globe' },
  glyphs: 'https://fonts.openmaptiles.org/{fontstack}/{range}.pbf',
  sources: {
    carto: {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        'https://b.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        'https://c.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
        'https://d.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
      ],
      tileSize: 256,
      attribution: '© OpenStreetMap © CARTO',
    },
  },
  layers: [
    { id: 'space', type: 'background', paint: { 'background-color': '#04060c' } },
    { id: 'carto', type: 'raster', source: 'carto', paint: { 'raster-opacity': 0.82 } },
  ],
  sky: {
    'sky-color': '#0a1226',
    'sky-horizon-blend': 0.6,
    'horizon-color': '#1d3e63',
    'horizon-fog-blend': 0.7,
    'fog-color': '#08101f',
    'fog-ground-blend': 0.4,
    'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 0.95, 4, 0.45, 8, 0.0],
  },
};

// Additive-glow blend (luma.gl v9 string params) for the halo layers.
const ADDITIVE = {
  blend: true,
  blendColorSrcFactor: 'src-alpha',
  blendColorDstFactor: 'one',
  blendAlphaSrcFactor: 'one',
  blendAlphaDstFactor: 'one',
  blendColorOperation: 'add',
  blendAlphaOperation: 'add',
};

const sqrtScale = (v, k) => Math.sqrt(Math.max(0, v)) * k;

function buildLayers({ ports, chokepoints, lanes, flags, pulse, selectedId, onSelectFlag }) {
  return [
    // --- shipping lanes (great-circle arcs) -------------------------------
    new ArcLayer({
      id: 'lanes',
      data: lanes,
      getSourcePosition: (d) => d.from,
      getTargetPosition: (d) => d.to,
      getSourceColor: [...LANE, 10],
      getTargetColor: [...LANE, 130],
      getWidth: (d) => 0.6 + d.intensity * 2.2,
      greatCircle: true,
      parameters: ADDITIVE,
    }),

    // --- ports: faint additive halo + bright core -------------------------
    new ScatterplotLayer({
      id: 'ports-halo',
      data: ports,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => sqrtScale(d.vessels, 2.4),
      radiusUnits: 'pixels',
      radiusMinPixels: 1.5,
      radiusMaxPixels: 26,
      getFillColor: [...CYAN, 26],
      parameters: ADDITIVE,
      pickable: false,
    }),
    new ScatterplotLayer({
      id: 'ports-core',
      data: ports,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => sqrtScale(d.vessels, 0.7),
      radiusUnits: 'pixels',
      radiusMinPixels: 0.6,
      radiusMaxPixels: 6,
      getFillColor: [...CYAN, 190],
      pickable: true,
      onClick: () => {},
    }),

    // --- chokepoints: amber halo + ringed core ----------------------------
    new ScatterplotLayer({
      id: 'choke-halo',
      data: chokepoints,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => sqrtScale(d.n_total, 1.7),
      radiusUnits: 'pixels',
      radiusMinPixels: 6,
      radiusMaxPixels: 46,
      getFillColor: [...AMBER, 34],
      parameters: ADDITIVE,
      pickable: false,
    }),
    new ScatterplotLayer({
      id: 'choke-core',
      data: chokepoints,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => 3 + sqrtScale(d.n_total, 0.32),
      radiusUnits: 'pixels',
      radiusMinPixels: 3,
      radiusMaxPixels: 11,
      getFillColor: [...AMBER, 235],
      stroked: true,
      lineWidthMinPixels: 1,
      getLineColor: [255, 220, 170, 220],
      pickable: true,
    }),

    // --- flags: pulsing severity rings ------------------------------------
    new ScatterplotLayer({
      id: 'flags-pulse',
      data: flags,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 1,
      radiusUnits: 'pixels',
      radiusScale: 10 + pulse * 16,
      radiusMinPixels: 10 + pulse * 16,
      radiusMaxPixels: 60,
      stroked: true,
      filled: true,
      getFillColor: (d) => severityColor(d.severity, 18),
      getLineColor: (d) => severityColor(d.severity, Math.round(120 + pulse * 110)),
      lineWidthMinPixels: 1.5,
      getLineWidth: (d) => (d.flag_id === selectedId ? 3 : 1.5),
      updateTriggers: { getLineWidth: selectedId },
      parameters: ADDITIVE,
      pickable: true,
      onClick: (info) => info.object && onSelectFlag(info.object),
    }),
  ];
}

export default function Globe({ snapshot, lanes, flags, selectedFlag, onSelectFlag, mapApiRef }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const overlayRef = useRef(null);
  const stateRef = useRef({ pulse: 0, lastInteract: 0, ready: false });
  const propsRef = useRef({ flags, selectedFlag, onSelectFlag });
  propsRef.current = { flags, selectedFlag, onSelectFlag };

  // Stable data refs so deck.gl reuses GPU buffers across animation frames.
  const dataRef = useRef({ ports: [], chokepoints: [], lanes: [] });
  dataRef.current = {
    ports: snapshot?.ports ?? [],
    chokepoints: snapshot?.chokepoints ?? [],
    lanes: lanes ?? [],
  };

  // --- create the map once ------------------------------------------------
  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [55, 22],
      zoom: 1.55,
      minZoom: 0.8,
      maxZoom: 7,
      pitch: 0,
      bearing: 0,
      attributionControl: { compact: true },
      dragRotate: false,
    });
    map.scrollZoom.setWheelZoomRate(1 / 200);
    mapRef.current = map;

    const overlay = new MapboxOverlay({
      interleaved: true,
      layers: [],
      getTooltip: ({ object, layer }) => {
        if (!object) return null;
        if (layer?.id?.startsWith('flags')) {
          return { html: `<b>${object.entity}</b><br/>${object.headline}`, className: 'fr-tip' };
        }
        if (layer?.id?.startsWith('choke')) {
          const pct = object.pct_change != null ? ` · ${object.pct_change > 0 ? '+' : ''}${object.pct_change}% vs 28d` : '';
          return { html: `<b>${object.name}</b><br/>${object.n_total} vessels/day${pct}`, className: 'fr-tip' };
        }
        if (layer?.id?.startsWith('ports')) {
          return { html: `<b>${object.name}</b>${object.country ? ', ' + object.country : ''}<br/>${object.vessels.toLocaleString()} vessels/yr`, className: 'fr-tip' };
        }
        return null;
      },
    });
    map.addControl(overlay);
    overlayRef.current = overlay;

    const bump = () => (stateRef.current.lastInteract = performance.now());
    ['mousedown', 'wheel', 'touchstart', 'dragstart'].forEach((e) => map.on(e, bump));

    map.on('load', () => {
      stateRef.current.ready = true;
    });

    // Expose a small imperative API (fly-to) to the parent.
    if (mapApiRef) {
      mapApiRef.current = {
        flyTo: (lon, lat) => {
          stateRef.current.lastInteract = performance.now() + 4000; // pause spin
          map.flyTo({ center: [lon, lat], zoom: 3.4, duration: 2400, essential: true });
        },
      };
    }

    // --- single rAF loop: pulse + idle auto-rotate + push deck layers -----
    let raf;
    const t0 = performance.now();
    const tick = (t) => {
      const st = stateRef.current;
      st.pulse = (Math.sin((t - t0) / 620) + 1) / 2;

      // gentle attract-mode spin when idle
      if (st.ready && t - st.lastInteract > 4200 && !map.isMoving()) {
        const c = map.getCenter();
        map.setCenter([c.lng + 0.045, c.lat]);
      }

      const { flags: fl, selectedFlag: sel, onSelectFlag: sl } = propsRef.current;
      overlay.setProps({
        layers: buildLayers({
          ...dataRef.current,
          flags: fl ?? [],
          pulse: st.pulse,
          selectedId: sel?.flag_id ?? null,
          onSelectFlag: sl,
        }),
      });
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    return () => {
      cancelAnimationFrame(raf);
      map.remove();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={containerRef} className="fr-globe" />;
}
