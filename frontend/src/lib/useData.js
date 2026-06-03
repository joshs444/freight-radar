import { useEffect, useState } from 'react';

// Vite serves /public at the root; the exporter writes these three files.
const FILES = {
  snapshot: 'data/snapshot.json',
  lanes: 'data/lanes.json',
  flags: 'data/flags.json',
};

export function useData() {
  const [state, setState] = useState({ loading: true, error: null, data: null });

  useEffect(() => {
    let alive = true;
    const base = import.meta.env.BASE_URL || '/';
    Promise.all(
      Object.values(FILES).map((f) =>
        fetch(base + f).then((r) => {
          if (!r.ok) throw new Error(`${f}: ${r.status}`);
          return r.json();
        })
      )
    )
      .then(([snapshot, lanes, flags]) => {
        if (!alive) return;
        setState({ loading: false, error: null, data: { snapshot, lanes, flags } });
      })
      .catch((e) => alive && setState({ loading: false, error: e.message, data: null }));
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
