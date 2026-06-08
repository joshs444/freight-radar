import { useEffect, useState } from 'react';
import type {
  AppData,
  Snapshot,
  Lane,
  Flag,
  Timeseries,
  Ships,
  ExposureSummary,
  News,
  NewsGeo,
  Quakes,
  Eonet,
  Marine,
  Tides,
  Streamflow,
  Market,
  Stress,
  Brief,
  Events,
  World,
  Disruptions,
  Gatun,
  Weather,
  Wind,
  SignalsFdr,
} from '../types.ts';

interface DataState {
  loading: boolean;
  error: string | null;
  data: AppData | null;
}

// Vite serves /public at the root; the exporters write these files.
const CORE = {
  snapshot: 'data/snapshot.json',
  lanes: 'data/lanes.json',
  flags: 'data/flags.json',
};

export function useData(): DataState {
  const [state, setState] = useState<DataState>({ loading: true, error: null, data: null });

  useEffect(() => {
    let alive = true;
    const base = import.meta.env.BASE_URL || '/';
    const getJson = <T>(f: string): Promise<T> =>
      fetch(base + f).then((r) => {
        if (!r.ok) throw new Error(`${f}: ${r.status}`);
        return r.json() as Promise<T>;
      });

    Promise.all([
      getJson<Snapshot>(CORE.snapshot),
      getJson<Lane[]>(CORE.lanes),
      getJson<Flag[]>(CORE.flags),
    ])
      .then(async ([snapshot, lanes, flags]) => {
        // timeseries + ships + exposure + news + stress/brief/events are optional —
        // features hide if absent (never block the core globe on a missing sidecar).
        const [
          timeseries,
          ships,
          exposure,
          news,
          newsGeo,
          quakes,
          eonet,
          marine,
          tides,
          streamflow,
          market,
          stress,
          brief,
          events,
          world,
          disruptions,
          gatun,
          weather,
          wind,
          signals,
        ] = await Promise.all([
          getJson<Timeseries>('data/timeseries.json').catch(() => null),
          getJson<Ships>('data/ships.json').catch(() => null),
          getJson<ExposureSummary>('data/exposure.json').catch(() => null),
          getJson<News>('data/news.json').catch(() => null),
          getJson<NewsGeo>('data/news_geo.json').catch(() => null),
          getJson<Quakes>('data/quakes.json').catch(() => null),
          getJson<Eonet>('data/eonet.json').catch(() => null),
          getJson<Marine>('data/marine.json').catch(() => null),
          getJson<Tides>('data/tides.json').catch(() => null),
          getJson<Streamflow>('data/streamflow.json').catch(() => null),
          getJson<Market>('data/market.json').catch(() => null),
          getJson<Stress>('data/stress.json').catch(() => null),
          getJson<Brief>('data/brief.json').catch(() => null),
          getJson<Events>('data/events.json').catch(() => null),
          getJson<World>('data/world.json').catch(() => null),
          getJson<Disruptions>('data/disruptions.json').catch(() => null),
          getJson<Gatun>('data/gatun.json').catch(() => null),
          getJson<Weather>('data/weather.json').catch(() => null),
          getJson<Wind>('data/wind.json').catch(() => null),
          getJson<SignalsFdr>('data/signals_fdr.json').catch(() => null),
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
            newsGeo,
            quakes,
            eonet,
            marine,
            tides,
            streamflow,
            market,
            stress,
            brief,
            events,
            world,
            disruptions,
            gatun,
            weather,
            wind,
            signals,
          },
        });
      })
      .catch((e: Error) => alive && setState({ loading: false, error: e.message, data: null }));
    return () => {
      alive = false;
    };
  }, []);

  return state;
}
