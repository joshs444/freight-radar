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

function buildLayers({ ports, chokepoints, lanes, flags, ships, storms, tripTime, tMax, pulse, selectedId, onSelectFlag }) {
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

    // ports — faint dark dust (no glow); clean pinpricks on the light globe.
    // radiusMinPixels >= 1.2 keeps every dot at least a full pixel so they don't
    // shimmer/blink at low zoom or while the map is moving.
    new ScatterplotLayer({
      id: 'ports',
      data: ports,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => sqrtScale(d.vessels, 0.34),
      radiusUnits: 'pixels',
      radiusMinPixels: 1.3,
      radiusMaxPixels: 3,
      getFillColor: [...PORT, 150],
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

    // active tropical cyclones (live NHC + GDACS) — a soft storm-blue halo that
    // breathes gently + a crisp core dot exactly on position (no harsh expanding ring)
    new ScatterplotLayer({
      id: 'storms-halo',
      data: storms || [],
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 1,
      radiusUnits: 'pixels',
      radiusMinPixels: 13 + pulse * 4,
      radiusMaxPixels: 13 + pulse * 4,
      filled: true,
      stroked: false,
      getFillColor: [47, 93, 153, 30],
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
      getFillColor: [47, 93, 153, 205],
      getLineColor: [255, 255, 255, 235],
      lineWidthMinPixels: 1.6,
      pickable: true,
    }),

    // flags — a soft severity-tinted glow that breathes gently (signals "active"
    // without the old expanding sonar ring) + a crisp filled core with a white ring,
    // centered exactly on the entity so the position reads precisely. The core is the
    // click/pick target.
    new ScatterplotLayer({
      id: 'flags-halo',
      data: flags,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: 1,
      radiusUnits: 'pixels',
      radiusMinPixels: 15 + pulse * 4,
      radiusMaxPixels: 15 + pulse * 4,
      filled: true,
      stroked: false,
      getFillColor: (d) => severityColor(d.severity, 26),
    }),
    new ScatterplotLayer({
      id: 'flags-ring',
      data: flags,
      getPosition: (d) => [d.lon, d.lat],
      getRadius: (d) => (d.flag_id === selectedId ? 8 : 6.5),
      radiusUnits: 'pixels',
      radiusMinPixels: 6.5,
      radiusMaxPixels: 8,
      filled: true,
      stroked: true,
      getFillColor: (d) => severityColor(d.severity, 235),
      getLineColor: [255, 255, 255, 255],
      lineWidthMinPixels: 2,
      getLineWidth: (d) => (d.flag_id === selectedId ? 3.2 : 2),
      updateTriggers: { getLineWidth: selectedId, getRadius: selectedId },
      pickable: true,
      onClick: (info) => info.object && onSelectFlag(info.object),
    }),
  ];
}

export default function Globe({ snapshot, lanes, flags, ships, storms, selectedFlag, onSelectFlag, mapApiRef }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const overlayRef = useRef(null);
  const stateRef = useRef({ pulse: 0, ready: false, engaged: false });
  const propsRef = useRef({ flags, selectedFlag, onSelectFlag });
  propsRef.current = { flags, selectedFlag, onSelectFlag };

  const dataRef = useRef({ ports: [], chokepoints: [], lanes: [], ships: [], storms: [], tMax: 100 });
  dataRef.current = {
    ports: snapshot?.ports ?? [],
    chokepoints: snapshot?.chokepoints ?? [],
    lanes: lanes ?? [],
    ships: ships?.ships ?? [],
    storms: storms ?? [],
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
      pickingRadius: 6,   // forgiving hover/click — grab a dot from a few px away
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
        if (layer?.id === 'storms') {
          const wind = object.max_wind_kmh ? ` · ${object.max_wind_kmh} km/h` : '';
          return { html: `🌀 <b>${object.name}</b> (${object.category})<br/>${object.basin}${wind} · live ${object.agency}`, className: 'fr-tip' };
        }
        return null;
      },
    });
    map.addControl(overlay);
    overlayRef.current = overlay;

    // The FIRST user interaction engages the map and permanently kills the intro
    // auto-rotate — once you're driving, it never drifts on you again.
    const engage = () => { stateRef.current.engaged = true; };
    ['mousedown', 'wheel', 'touchstart', 'dragstart', 'keydown'].forEach((e) => map.on(e, engage));
    map.on('load', () => {
      stateRef.current.ready = true;
      map.resize();
    });

    if (mapApiRef) {
      mapApiRef.current = {
        flyTo: (lon, lat) => {
          stateRef.current.engaged = true;   // flying to a row also stops the spin
          map.flyTo({ center: [lon, lat], zoom: 3.4, duration: 2400, essential: true });
        },
      };
    }

    let raf;
    const t0 = performance.now();
    const AIS_LOOP_MS = 9000;
    const tick = (t) => {
      const st = stateRef.current;
      st.pulse = (Math.sin((t - t0) / 1100) + 1) / 2;   // calm, slow breathe (~7s)
      const moving = map.isMoving();
      const tMax = dataRef.current.tMax;
      const tripTime = ((t - t0) % AIS_LOOP_MS) / AIS_LOOP_MS * tMax;

      // gentle intro spin — only until the user first engages, then never again
      if (st.ready && !st.engaged && !moving) {
        const c = map.getCenter();
        map.setCenter([c.lng + 0.04, c.lat]);
      }

      // Only push new deck layers while the camera is idle. During a pan/zoom the
      // interleaved overlay already redraws the existing layers in lockstep with the
      // basemap; re-instantiating them mid-gesture is exactly what made the dots and
      // alert rings blink. Freezing the animation during movement keeps it rock-steady.
      if (!moving) {
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
      }
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
