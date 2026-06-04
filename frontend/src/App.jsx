import { useRef, useState, useCallback, useMemo } from 'react';
import Globe from './Globe.jsx';
import DataFeed from './components/DataFeed.jsx';
import TimeScrubber from './components/TimeScrubber.jsx';
import StressGauge from './components/StressGauge.jsx';
import Chat from './components/Chat.jsx';
import WorldRibbon from './components/WorldRibbon.jsx';
import { useData } from './lib/useData.js';

export default function App() {
  const { loading, error, data } = useData();
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState('all');
  const [scrubIndex, setScrubIndex] = useState(null);
  const [playing, setPlaying] = useState(false);
  const mapApiRef = useRef(null);

  const ts = data?.timeseries;

  // --- the monitor universe: chokepoints + flagged ports + top ports ------
  const sets = useMemo(() => {
    if (!data) return { choke: [], portFlags: [], topPorts: [] };
    const flagByPort = {};
    (data.flags || [])
      .filter((f) => f.lifecycle !== 'resolved')
      .forEach((f) => { flagByPort[f.portid] = f; });

    const choke = (data.snapshot?.chokepoints || []).map((c) => {
      const flag = flagByPort[c.portid] || null;
      return {
        id: c.portid, name: c.name, type: 'chokepoint', lat: c.lat, lon: c.lon,
        // flagged rows show the flag's own pct (e.g. Hormuz -92% persistent), not
        // the noisy latest-vs-28d snapshot value (+124%); normals show the snapshot.
        metric: flag ? flag.pct_change : c.pct_change,
        n_total: c.n_total, baseline: c.baseline,
        flag, severity: flag ? flag.severity : null, critical: !!flag,
        weight: c.n_total || 0,
      };
    });
    const chokeIds = new Set(choke.map((c) => c.id));
    const portFlags = Object.values(flagByPort)
      .filter((f) => !chokeIds.has(f.portid))
      .map((f) => ({
        id: f.portid, name: f.entity, type: 'port', lat: f.lat, lon: f.lon,
        metric: f.pct_change, flag: f, severity: f.severity, critical: true, weight: 1e9,
      }));
    const topPorts = [...(data.snapshot?.ports || [])]
      .sort((a, b) => b.vessels - a.vessels)
      .slice(0, 40)
      .filter((p) => !flagByPort[p.portid])
      .map((p) => ({
        id: p.portid, name: p.name, type: 'port', lat: p.lat, lon: p.lon,
        metric: null, vessels: p.vessels, flag: null, critical: false, weight: p.vessels || 0,
      }));
    return { choke, portFlags, topPorts };
  }, [data]);

  // critical first (by severity), then normal by real traffic — not by noisy %
  const byCritThenSeverity = (a, b) =>
    b.critical - a.critical || (b.severity || 0) - (a.severity || 0) ||
    (b.weight || 0) - (a.weight || 0);

  const rows = useMemo(() => {
    const { choke, portFlags, topPorts } = sets;
    let list;
    if (filter === 'critical') list = [...choke, ...portFlags].filter((e) => e.critical);
    else if (filter === 'chokepoints') list = choke;
    else if (filter === 'ports') list = [...portFlags, ...topPorts];
    else list = [...choke, ...portFlags];
    return [...list].sort(byCritThenSeverity);
  }, [sets, filter]);

  const criticalCount = useMemo(
    () => [...sets.choke, ...sets.portFlags].filter((e) => e.critical).length,
    [sets]
  );

  const selectEntity = useCallback((e) => {
    setSelected(e);
    if (e && e.lat != null && mapApiRef.current) mapApiRef.current.flyTo(e.lon, e.lat);
  }, []);

  // brief bullet / stress gauge → jump to an entity by portid (fly globe + open row)
  const pickByPortid = useCallback((portid) => {
    const all = [...sets.choke, ...sets.portFlags, ...sets.topPorts];
    const e = all.find((x) => x.id === portid);
    if (e) { setFilter('all'); selectEntity(e); }
  }, [sets, selectEntity]);

  // a flag ring clicked on the globe -> select the matching feed entity
  const onSelectFlagFromGlobe = useCallback((flag) => {
    selectEntity({
      id: flag.portid, name: flag.entity, type: flag.kind.startsWith('chokepoint') ? 'chokepoint' : 'port',
      lat: flag.lat, lon: flag.lon, metric: flag.pct_change, flag, severity: flag.severity, critical: true,
    });
  }, [selectEntity]);

  // globe replay: scrub swaps chokepoint glow + which flags have fired
  const globeView = useMemo(() => {
    if (!data) return { snapshot: null, flags: [] };
    if (scrubIndex === null || !ts) {
      return {
        snapshot: data.snapshot,
        flags: (data.flags || []).filter((f) => f.lifecycle !== 'resolved'),
      };
    }
    const day = ts.dates[scrubIndex];
    const chokepoints = ts.chokepoints.map((c) => ({
      portid: c.portid, name: c.name, lat: c.lat, lon: c.lon,
      n_total: c.values[scrubIndex], pct_change: null,
    }));
    return { snapshot: { ...data.snapshot, chokepoints }, flags: ts.flags.filter((f) => f.as_of <= day) };
  }, [data, ts, scrubIndex]);

  if (error) {
    return (
      <div className="fr-fallback">
        <h1>Freight Radar</h1>
        <p>Could not load the snapshot ({error}).</p>
        <p className="dim">Run the exporter: <code>python -m freight_radar.publish</code></p>
      </div>
    );
  }

  const asOf = data?.snapshot?.as_of ?? '—';
  const source = data?.snapshot?.source ?? 'IMF PortWatch';

  return (
    <div className="fr-app">
      <header className="fr-topbar">
        <div className="fr-brand">
          <span className="fr-logo" aria-hidden>◐</span>
          <div>
            <h1>FREIGHT RADAR</h1>
            <p className="fr-tag">Ocean-freight chokepoints, monitored — disruptions auto-flagged from IMF PortWatch.</p>
          </div>
        </div>
        {data?.stress?.available && (
          <StressGauge
            stress={data.stress}
            onOpen={() => data.stress.contributors?.[0] && pickByPortid(data.stress.contributors[0].portid)}
          />
        )}
        <div className="fr-asof">
          <span className="fr-dot" /> {source}<br />
          data as of <b>{asOf}</b>
        </div>
      </header>

      {data?.world?.available && <WorldRibbon world={data.world} />}

      <div className="fr-main">
        <section className="fr-stage">
          {data && (
            <Globe
              snapshot={globeView.snapshot}
              lanes={data.lanes}
              flags={globeView.flags}
              ships={data.ships}
              selectedFlag={selected?.flag || null}
              onSelectFlag={onSelectFlagFromGlobe}
              mapApiRef={mapApiRef}
            />
          )}
          <div className="fr-legend">
            <span><i className="sw amber" /> chokepoint</span>
            <span><i className="sw port" /> port</span>
            <span><i className="sw pulse" /> flagged</span>
            <span className={`fr-ais ais-${data?.ships?.mode || 'offline'}`}>
              <i className="sw ais" /> AIS · {data?.ships?.mode === 'live' ? 'live' : data?.ships?.mode === 'demo' ? 'simulated' : 'offline'}
            </span>
          </div>
          {ts && ts.dates?.length > 1 && (
            <TimeScrubber
              timeseries={ts}
              index={scrubIndex}
              playing={playing}
              onChange={(i) => setScrubIndex(i)}
              onPlayToggle={() => setPlaying((p) => !p)}
              onLive={() => { setPlaying(false); setScrubIndex(null); }}
            />
          )}
          {loading && <div className="fr-loading">acquiring signal…</div>}
        </section>

        {data && (
          <DataFeed
            rows={rows}
            filter={filter}
            setFilter={setFilter}
            criticalCount={criticalCount}
            exposure={data.exposure}
            brief={data.brief}
            onPickEntity={pickByPortid}
            series={ts?.series}
            dates={ts?.dates}
            news={data.news?.items}
            market={data.market}
            selected={selected}
            onSelect={selectEntity}
            asOf={asOf}
            source={source}
          />
        )}
      </div>

      {data && <Chat data={data} onPickEntity={pickByPortid} />}
    </div>
  );
}
