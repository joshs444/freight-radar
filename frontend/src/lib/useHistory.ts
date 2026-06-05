import { useCallback, useEffect, useMemo, useState } from 'react';
import type { History, HistoryEvent, GlobeSnapshot, GlobeFlag, SnapshotPort } from '../types.ts';

// Owns the "play through history" state: lazy-loads history.json, runs the playhead, and
// derives — for the playhead week — a synthetic globe view where each chokepoint is
// recoloured/flared by how far its throughput sits from its own normal, plus which
// curated event is in frame. App stays a thin wiring layer.

const FLAG_DEV = 0.2; // |deviation from normal| beyond which a chokepoint lights up
const STEP_MS = 80; // playhead advance interval (~12 weeks/sec)
const NEAR_MS = 9 * 864e5; // an event stays "in frame" within ~9 days of its span

export function useHistory(livePorts: SnapshotPort[]) {
  const [history, setHistory] = useState<History | null>(null);
  const [mode, setMode] = useState(false);
  const [week, setWeek] = useState(0);
  const [playing, setPlaying] = useState(false);

  const enter = useCallback(async () => {
    let h = history;
    if (!h) {
      try {
        const base = import.meta.env.BASE_URL || '/';
        const r = await fetch(`${base}data/history.json`);
        if (r.ok) {
          h = (await r.json()) as History;
          setHistory(h);
        }
      } catch {
        /* ignore — the button just won't open History */
      }
    }
    if (h) {
      setWeek(0); // start at 2019 so "play 2019 → now" sweeps forward through the shocks
      setMode(true);
    }
  }, [history]);

  const exit = useCallback(() => {
    setMode(false);
    setPlaying(false);
  }, []);

  const togglePlay = useCallback(() => {
    setPlaying((p) => {
      if (!p && history && week >= history.dates.length - 1) setWeek(0); // replay from start
      return !p;
    });
  }, [history, week]);

  useEffect(() => {
    if (!mode || !playing || !history) return;
    const id = window.setInterval(() => {
      setWeek((w) => {
        if (w >= history.dates.length - 1) {
          setPlaying(false);
          return w;
        }
        return w + 1;
      });
    }, STEP_MS);
    return () => window.clearInterval(id);
  }, [mode, playing, history]);

  const view = useMemo(() => {
    if (!history) {
      return {
        snapshot: null as GlobeSnapshot | null,
        flags: [] as GlobeFlag[],
        event: null as HistoryEvent | null,
      };
    }
    const w = Math.min(week, history.dates.length - 1);
    const date = history.dates[w];

    const chokepoints = history.chokepoints.map((c) => {
      const v = c.values[w] ?? 0;
      const pct = c.normal ? Math.round(((v - c.normal) / c.normal) * 100) : 0;
      return {
        portid: c.portid,
        name: c.name,
        lat: c.lat,
        lon: c.lon,
        n_total: v,
        pct_change: pct,
      };
    });
    const snapshot: GlobeSnapshot = {
      as_of: date,
      generated_at: history.generated_at,
      source: history.source,
      ports: livePorts,
      chokepoints,
    };

    const flags: GlobeFlag[] = history.chokepoints.flatMap((c) => {
      if (!c.normal) return [];
      const v = c.values[w] ?? 0;
      const dev = (v - c.normal) / c.normal;
      if (Math.abs(dev) < FLAG_DEV) return [];
      const pct = Math.round(dev * 100);
      return [
        {
          flag_id: `${c.portid}@${w}`,
          entity: c.name,
          portid: c.portid,
          lat: c.lat,
          lon: c.lon,
          severity: Math.min(100, Math.round(Math.abs(dev) * 100)),
          kind: dev < 0 ? 'chokepoint_throughput_drop' : 'chokepoint_throughput_spike',
          headline: `${pct > 0 ? '+' : ''}${pct}% vs normal · ${date}`,
          pct_change: pct,
        },
      ];
    });

    const t = Date.parse(date);
    const inFrame = history.events.filter((e) => {
      const from = Date.parse(e.from ?? e.date) - NEAR_MS;
      const to = Date.parse(e.to ?? e.date) + NEAR_MS;
      return t >= from && t <= to;
    });
    // when several events overlap (e.g. Panama drought + Red Sea), show the newest onset
    const event = inFrame.length
      ? inFrame.reduce((a, b) => (Date.parse(b.date) >= Date.parse(a.date) ? b : a))
      : null;

    return { snapshot, flags, event };
  }, [history, week, livePorts]);

  return { history, mode, week, playing, enter, exit, setWeek, togglePlay, ...view };
}
