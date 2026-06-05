import { useEffect, useState } from 'react';

// Vite serves /public at the root; the exporters write these files.
const CORE = {
  snapshot: 'data/snapshot.json',
  lanes: 'data/lanes.json',
  flags: 'data/flags.json',
};

export function useData() {
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    let alive = true;
    const base = import.meta.env.BASE_URL || '/';
    const getJson = (f) =>
      fetch(base + f).then((r) => {
        if (!r.ok) throw new Error(`${f}: ${r.status}`);
        return r.json();
      });

    Promise.all(Object.values(CORE).map(getJson))
      .then(async ([snapshot, lanes, flags]) => {
        // timeseries + ships + exposure + news + stress/brief/events are optional —
        // features hide if absent (never block the core globe on a missing sidecar).
        const [
          timeseries,
          ships,
          exposure,
          news,
          market,
          stress,
          brief,
          events,
          world,
          disruptions,
          gatun,
          weather,
          wind,
        ] = await Promise.all([
          getJson('data/timeseries.json').catch(() => null),
          getJson('data/ships.json').catch(() => null),
          getJson('data/exposure.json').catch(() => null),
          getJson('data/news.json').catch(() => null),
          getJson('data/market.json').catch(() => null),
          getJson('data/stress.json').catch(() => null),
          getJson('data/brief.json').catch(() => null),
          getJson('data/events.json').catch(() => null),
          getJson('data/world.json').catch(() => null),
          getJson('data/disruptions.json').catch(() => null),
          getJson('data/gatun.json').catch(() => null),
          getJson('data/weather.json').catch(() => null),
          getJson('data/wind.json').catch(() => null),
        ]);
        if (!alive) return;
        setState({
          loading: false,
          error: null,
          data: {
            snapshot,
            lanes,
            flags,
            timeseries,
            ships,
            exposure,
            news,
            market,
            stress,
            brief,
            events,
            world,
            disruptions,
            gatun,
            weather,
            wind,
          },
        });
      })
      .catch((e) => alive && setState({ loading: false, error: e.message, data: null }));
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
