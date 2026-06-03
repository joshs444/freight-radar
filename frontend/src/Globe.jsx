import { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import { MapboxOverlay } from '@deck.gl/mapbox';
import { ScatterplotLayer, ArcLayer } from '@deck.gl/layers';
import { TripsLayer } from '@deck.gl/geo-layers';
import { AMBER, PORT, LANE, severityColor } from './lib/colors.js';

// Clean, token-free LIGHT basemap (CARTO Positron) draped on the v5 globe.
const STYLE = {
  version: 8,
  projection: { type: 'globe' },
  sources: {
    carto: {
      type: 'raster',
      tiles: [
        'https://a.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
        'https://b.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
        'https://c.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
        'https://d.basemaps.cartocdn.com/light_all/{z}/{x}/{y}.png',
      ],
      tileSize: 256,
      attribution: '© OpenStreetMap © CARTO',
    },
  },
  layers: [
    { id: 'space', type: 'background', paint: { 'background-color': '#e9edf3' } },
    { id: 'carto', type: 'raster', source: 'carto', paint: { 'raster-opacity': 1 } },
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

const sqrtScale = (v, k) => Math.sqrt(Math.max(0, v)) * k;

function buildLayers({ ports, chokepoints, lanes, flags, ships, tripTime, tMax, pulse, selectedId, onSelectFlag }) {
  return [
    // shipping lanes — thin, soft great-circle arcs
    new ArcLayer({
      id: 'lanes',
      data: lanes,
      getSourcePosition: (d) => d.from,
      getTargetPosition: (d) => d.to,
      getSourceColor: [...LANE, 18],
      getTargetColor: [...LANE, 70],
      getWidth: (d) => 0.5 + d.intensity * 1.4,
      greatCircle: true,
    }),

    // optional ship trails (garnish) — medium slate so they read on light
    new TripsLayer({
      id: 'ships',
      data: ships || [],
      getPath: (d) => d.path.map((p) => [p[0], p[1]]),
      getTimestamps: (d) => d.path.map((p) => p[2]),
      getColor: [80, 110, 140],
      opacity: 0.55,
      widthMinPixels: 1.4,
      capRounded: true,
      jointRounded: true,
      trailLength: Math.max(18, tMax * 0.35),
      currentTime: tripTime,
      fadeTrail: true,
    }),

    // ports — faint dark dust (no glow); clean pinpricks on the light globe
    new ScatterplotLayer({
      id: 'ports',
      data: ports,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => sqrtScale(d.vessels, 0.32),
      radiusUnits: 'pixels',
      radiusMinPixels: 0.5,
      radiusMaxPixels: 2.4,
      getFillColor: [...PORT, 120],
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
      getFillColor: [...AMBER, 255],
      stroked: true,
      lineWidthMinPixels: 1.4,
      getLineColor: [255, 255, 255, 235],
      pickable: true,
    }),

    // flags — pulsing severity ring (sonar ping) + a steady ring (click target)
    new ScatterplotLayer({
      id: 'flags-ping',
      data: flags,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 1,
      radiusUnits: 'pixels',
      radiusMinPixels: 12 + pulse * 22,
      radiusMaxPixels: 12 + pulse * 22,
      stroked: true,
      filled: false,
      getLineColor: (d) => severityColor(d.severity, Math.round((1 - pulse) * 150)),
      lineWidthMinPixels: 2,
      pickable: false,
    }),
    new ScatterplotLayer({
      id: 'flags-ring',
      data: flags,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 1,
      radiusUnits: 'pixels',
      radiusMinPixels: 11,
      radiusMaxPixels: 11,
      stroked: true,
      filled: true,
      getFillColor: (d) => severityColor(d.severity, 60),
      getLineColor: (d) => severityColor(d.severity, 255),
      lineWidthMinPixels: 2.4,
      getLineWidth: (d) => (d.flag_id === selectedId ? 3.6 : 2.4),
      updateTriggers: { getLineWidth: selectedId },
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

  const dataRef = useRef({ ports: [], chokepoints: [], lanes: [], ships: [], tMax: 100 });
  dataRef.current = {
    ports: snapshot?.ports ?? [],
    chokepoints: snapshot?.chokepoints ?? [],
    lanes: lanes ?? [],
    ships: ships?.ships ?? [],
    tMax: ships?.t_max ?? 100,
  };

  useEffect(() => {
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
        if (layer?.id === 'choke') {
          const pct = object.pct_change != null ? ` · ${object.pct_change > 0 ? '+' : ''}${object.pct_change}% vs 28d` : '';
          return { html: `<b>${object.name}</b><br/>${object.n_total} vessels/day${pct}`, className: 'fr-tip' };
        }
        if (layer?.id === 'ports') {
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
      map.resize();
    });

    if (mapApiRef) {
      mapApiRef.current = {
        flyTo: (lon, lat) => {
          stateRef.current.lastInteract = performance.now() + 4000;
          map.flyTo({ center: [lon, lat], zoom: 3.4, duration: 2400, essential: true });
        },
      };
    }

    let raf;
    const t0 = performance.now();
    const AIS_LOOP_MS = 9000;
    const tick = (t) => {
      const st = stateRef.current;
      st.pulse = (Math.sin((t - t0) / 620) + 1) / 2;
      const tMax = dataRef.current.tMax;
      const tripTime = ((t - t0) % AIS_LOOP_MS) / AIS_LOOP_MS * tMax;

      if (st.ready && t - st.lastInteract > 4200 && !map.isMoving()) {
        const c = map.getCenter();
        map.setCenter([c.lng + 0.04, c.lat]);
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
