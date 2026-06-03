import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { ScatterplotLayer, ArcLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
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
    { id: 'space', type: 'background', paint: { 'background-color': '#03050b' } },
    {
      id: 'carto',
      type: 'raster',
      source: 'carto',
      paint: {
        'raster-opacity': 0.62,
        'raster-saturation': -0.4,
        'raster-contrast': 0.04,
        'raster-brightness-min': 0.0,
      },
    },
  ],
  // Luminous blue atmospheric rim against deep space — the "whoa" edge light.
  sky: {
    'sky-color': '#0a1530',
    'sky-horizon-blend': 0.5,
    'horizon-color': '#2e74c0',
    'horizon-fog-blend': 0.6,
    'fog-color': '#0a1226',
    'fog-ground-blend': 0.55,
    'atmosphere-blend': ['interpolate', ['linear'], ['zoom'], 0, 1.0, 4, 0.55, 8, 0.0],
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

function buildLayers({ ports, chokepoints, lanes, flags, ships, tripTime, tMax, pulse, selectedId, onSelectFlag }) {
  return [
    // --- shipping lanes (great-circle arcs) -------------------------------
    new ArcLayer({
      id: 'lanes',
      data: lanes,
      getSourcePosition: (d) => d.from,
      getTargetPosition: (d) => d.to,
      getSourceColor: [...LANE, 38],
      getTargetColor: [...LANE, 200],
      getWidth: (d) => 1 + d.intensity * 3,
      greatCircle: true,
      parameters: ADDITIVE,
    }),

    // --- live/sim ship trails (optional garnish; empty-safe) --------------
    new TripsLayer({
      id: 'ships',
      data: ships || [],
      getPath: (d) => d.path.map((p) => [p[0], p[1]]),
      getTimestamps: (d) => d.path.map((p) => p[2]),
      getColor: [130, 225, 255],
      opacity: 0.85,
      widthMinPixels: 1.6,
      capRounded: true,
      jointRounded: true,
      trailLength: Math.max(18, tMax * 0.35),
      currentTime: tripTime,
      fadeTrail: true,
      parameters: ADDITIVE,
    }),

    // --- ports: faint ambient dust (no blooming halo) ---------------------
    new ScatterplotLayer({
      id: 'ports',
      data: ports,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => sqrtScale(d.vessels, 0.34),
      radiusUnits: 'pixels',
      radiusMinPixels: 0.4,
      radiusMaxPixels: 2.4,
      getFillColor: [108, 150, 178, 120],
      pickable: true,
    }),

    // --- chokepoints: amber halo + ringed core ----------------------------
    new ScatterplotLayer({
      id: 'choke-halo',
      data: chokepoints,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => 4 + sqrtScale(d.n_total, 1.15),
      radiusUnits: 'pixels',
      radiusMinPixels: 5,
      radiusMaxPixels: 26,
      getFillColor: [...AMBER, 40],
      parameters: ADDITIVE,
      pickable: false,
    }),
    new ScatterplotLayer({
      id: 'choke-core',
      data: chokepoints,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => 2.6 + sqrtScale(d.n_total, 0.22),
      radiusUnits: 'pixels',
      radiusMinPixels: 2.6,
      radiusMaxPixels: 7,
      getFillColor: [...AMBER, 255],
      stroked: true,
      lineWidthMinPixels: 1,
      getLineColor: [255, 226, 188, 210],
      pickable: true,
    }),

    // --- flags: outer sonar-ping ring (expands + fades with the pulse) -----
    new ScatterplotLayer({
      id: 'flags-ping',
      data: flags,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 1,
      radiusUnits: 'pixels',
      radiusMinPixels: 16 + pulse * 30,
      radiusMaxPixels: 16 + pulse * 30,
      stroked: true,
      filled: false,
      getLineColor: (d) => severityColor(d.severity, Math.round((1 - pulse) * 200)),
      lineWidthMinPixels: 2,
      parameters: ADDITIVE,
      pickable: false,
    }),
    // --- flags: steady severity ring (the click target) -------------------
    new ScatterplotLayer({
      id: 'flags-ring',
      data: flags,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 1,
      radiusUnits: 'pixels',
      radiusMinPixels: 13,
      radiusMaxPixels: 13,
      stroked: true,
      filled: true,
      getFillColor: (d) => severityColor(d.severity, 36),
      getLineColor: (d) =>
        severityColor(d.severity, d.flag_id === selectedId ? 255 : 190),
      lineWidthMinPixels: 2.2,
      getLineWidth: (d) => (d.flag_id === selectedId ? 3.5 : 2.2),
      updateTriggers: { getLineColor: selectedId, getLineWidth: selectedId },
      parameters: ADDITIVE,
      pickable: true,
      onClick: (info) => info.object && onSelectFlag(info.object),
    }),
  ];
}

export default function Globe({ snapshot, lanes, flags, ships, selectedFlag, onSelectFlag, mapApiRef }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const overlayRef = useRef(null);
  const stateRef = useRef({ pulse: 0, lastInteract: 0, ready: false });
  const propsRef = useRef({ flags, selectedFlag, onSelectFlag });
  propsRef.current = { flags, selectedFlag, onSelectFlag };

  // Stable data refs so deck.gl reuses GPU buffers across animation frames.
  const dataRef = useRef({ ports: [], chokepoints: [], lanes: [], ships: [], tMax: 100 });
  dataRef.current = {
    ports: snapshot?.ports ?? [],
    chokepoints: snapshot?.chokepoints ?? [],
    lanes: lanes ?? [],
    ships: ships?.ships ?? [],
    tMax: ships?.t_max ?? 100,
  };

  // --- create the map once ------------------------------------------------
  useEffect(() => {
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: STYLE,
      center: [78, 18],
      zoom: 1.72,
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
      map.resize(); // ensure canvas matches the (now sized) container
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
    const AIS_LOOP_MS = 9000;
    const tick = (t) => {
      const st = stateRef.current;
      st.pulse = (Math.sin((t - t0) / 620) + 1) / 2;
      const tMax = dataRef.current.tMax;
      const tripTime = ((t - t0) % AIS_LOOP_MS) / AIS_LOOP_MS * tMax;

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
          tripTime,
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
