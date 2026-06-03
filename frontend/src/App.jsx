import { useRef, useState, useCallback } from 'react';
import Globe from './Globe.jsx';
import IssuesRail from './components/IssuesRail.jsx';
import { useData } from './lib/useData.js';

export default function App() {
  const { loading, error, data } = useData();
  const [selectedFlag, setSelectedFlag] = useState(null);
  const mapApiRef = useRef(null);

  const onSelectFlag = useCallback((flag) => {
    setSelectedFlag(flag);
    if (flag && mapApiRef.current) mapApiRef.current.flyTo(flag.lon, flag.lat);
  }, []);

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
          snapshot={data.snapshot}
          lanes={data.lanes}
          flags={data.flags}
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

      {loading && <div className="fr-loading">acquiring signal…</div>}
    </div>
  );
}
