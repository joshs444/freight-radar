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
        // timeseries + ships are optional garnish — features hide if absent
        const [timeseries, ships] = await Promise.all([
          getJson('data/timeseries.json').catch(() => null),
          getJson('data/ships.json').catch(() => null),
        ]);
        if (!alive) return;
        setState({ loading: false, error: null, data: { snapshot, lanes, flags, timeseries, ships } });
      })
      .catch((e) => alive && setState({ loading: false, error: e.message, data: null }));
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
