import { useRef, useState, useCallback, useMemo } from 'react';
import Globe from './Globe.jsx';
import IssuesRail from './components/IssuesRail.jsx';
import TimeScrubber from './components/TimeScrubber.jsx';
import { useData } from './lib/useData.js';

export default function App() {
  const { loading, error, data } = useData();
  const [selectedFlag, setSelectedFlag] = useState(null);
  const [scrubIndex, setScrubIndex] = useState(null); // null = live (present)
  const [playing, setPlaying] = useState(false);
  const mapApiRef = useRef(null);

  const onSelectFlag = useCallback((flag) => {
    setSelectedFlag(flag);
    if (flag && mapApiRef.current) mapApiRef.current.flyTo(flag.lon, flag.lat);
  }, []);

  const ts = data?.timeseries;

  // When scrubbing, the globe replays that day: chokepoint glow uses the day's
  // real vessel count, and flags that had fired by then are shown.
  const display = useMemo(() => {
    if (!data) return { snapshot: null, flags: [] };
    if (scrubIndex === null || !ts) return { snapshot: data.snapshot, flags: data.flags };
    const day = ts.dates[scrubIndex];
    const chokepoints = ts.chokepoints.map((c) => ({
      portid: c.portid, name: c.name, lat: c.lat, lon: c.lon,
      n_total: c.values[scrubIndex], baseline: null, pct_change: null, as_of: day,
    }));
    const flags = ts.flags.filter((f) => f.as_of <= day);
    return { snapshot: { ...data.snapshot, chokepoints }, flags };
  }, [data, ts, scrubIndex]);

  if (error) {
    return (
      <div className="fr-fallback">
        <h1>Freight Radar</h1>
        <p>Could not load the snapshot ({error}).</p>
        <p className="dim">Run the exporter: <code>python -m freight_radar.export_snapshot</code></p>
      </div>
    );
  }

  const snapshot = data?.snapshot;
  const asOf = snapshot?.as_of ?? '—';
  const source = snapshot?.source ?? 'IMF PortWatch';

  return (
    <div className="fr-app">
      <div className="fr-stars" aria-hidden />
      {data && (
        <Globe
          snapshot={display.snapshot}
          lanes={data.lanes}
          flags={display.flags.filter((f) => f.lifecycle !== 'resolved')}
          ships={data.ships}
          selectedFlag={selectedFlag}
          onSelectFlag={onSelectFlag}
          mapApiRef={mapApiRef}
        />
      )}
      <div className="fr-vignette" aria-hidden />

      <header className="fr-head">
        <div className="fr-brand">
          <span className="fr-logo" aria-hidden>◑</span>
          <div>
            <h1>FREIGHT&nbsp;RADAR</h1>
            <p className="fr-tag">Ocean-freight chokepoints, glowing by real activity — disruptions auto-flagged.</p>
          </div>
        </div>
        <div className="fr-asof">
          <span className="fr-dot" /> {source}
          <br />
          data as of <b>{asOf}</b>
        </div>
      </header>

      <div className="fr-legend">
        <span><i className="sw amber" /> chokepoint</span>
        <span><i className="sw cyan" /> port</span>
        <span><i className="sw lane" /> lane</span>
        <span><i className="sw pulse" /> flagged issue</span>
        <span className={`fr-ais ais-${data?.ships?.mode || 'offline'}`}>
          <i className="sw ais" /> AIS · {data?.ships?.mode === 'live' ? 'live' : data?.ships?.mode === 'demo' ? 'simulated' : 'offline'}
        </span>
      </div>

      {data && (
        <IssuesRail
          flags={data.flags}
          selectedFlag={selectedFlag}
          onSelect={onSelectFlag}
          asOf={asOf}
          source={source}
        />
      )}

      {ts && ts.dates?.length > 1 && (
        <TimeScrubber
          timeseries={ts}
          index={scrubIndex}
          playing={playing}
          onChange={(i) => setScrubIndex(i)}
          onPlayToggle={() => setPlaying((p) => !p)}
          onLive={() => {
            setPlaying(false);
            setScrubIndex(null);
          }}
        />
      )}

      {loading && <div className="fr-loading">acquiring signal…</div>}
    </div>
  );
}
