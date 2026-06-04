import { useRef, useState, useCallback, useMemo, useEffect } from 'react';
import Globe from './Globe.jsx';
import DataFeed from './components/DataFeed.jsx';
import TimeScrubber from './components/TimeScrubber.jsx';
import StressGauge from './components/StressGauge.jsx';
import StressDetail from './components/StressDetail.jsx';
import Chat from './components/Chat.jsx';
import WorldRibbon from './components/WorldRibbon.jsx';
import SearchBox from './components/SearchBox.jsx';
import Onboarding from './components/Onboarding.jsx';
import { useData } from './lib/useData.js';
import { useWatchlist, notifyWatched } from './lib/useWatchlist.js';

export default function App() {
  const { loading, error, data } = useData();
  const [selected, setSelected] = useState(null);
  const [filter, setFilter] = useState('all');
  const [scrubIndex, setScrubIndex] = useState(null);
  const [playing, setPlaying] = useState(false);
  const [userExposure, setUserExposure] = useState(null);
  const [showStress, setShowStress] = useState(false);
  const { watched, toggle: toggleWatch } = useWatchlist();
  const mapApiRef = useRef(null);

  const ts = data?.timeseries;

  // uploaded trade data (if any) overrides the sample exposure + per-flag business
  const flags = userExposure?.flags ?? data?.flags;
  const exposureSummary = userExposure?.summary ?? data?.exposure;

  // when scrubbing, the feed reflects that past day: only flags that had fired by
  // then are "active", and chokepoint metrics come from the history at that date.
  const scrubDate = scrubIndex != null && ts ? ts.dates[scrubIndex] : null;

  // --- the monitor universe: chokepoints + flagged ports + top ports ------
  const sets = useMemo(() => {
    if (!data) return { choke: [], portFlags: [], topPorts: [] };
    const flagByPort = {};
    (flags || [])
      .filter((f) => f.lifecycle !== 'resolved' && (!scrubDate || f.as_of <= scrubDate))
      .forEach((f) => { flagByPort[f.portid] = f; });
    const seriesAt = (portid, baseline) => {
      const v = ts?.series?.[portid]?.values?.[scrubIndex];
      if (v == null || !baseline) return null;
      return Math.round(((v - baseline) / baseline) * 1000) / 10;
    };

    const choke = (data.snapshot?.chokepoints || []).map((c) => {
      const flag = flagByPort[c.portid] || null;
      return {
        id: c.portid, name: c.name, type: 'chokepoint', lat: c.lat, lon: c.lon,
        // flagged rows show the flag's own pct (e.g. Hormuz -92% persistent), not
        // the noisy latest-vs-28d snapshot value (+124%); normals show the snapshot.
        // while scrubbing, normals show the value at the scrubbed date.
        metric: flag ? flag.pct_change : (scrubDate ? seriesAt(c.portid, c.baseline) : c.pct_change),
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
  }, [data, flags, scrubDate, scrubIndex, ts]);

  // critical first (by severity), then normal by real traffic — not by noisy %
  const byCritThenSeverity = (a, b) =>
    b.critical - a.critical || (b.severity || 0) - (a.severity || 0) ||
    (b.weight || 0) - (a.weight || 0);

  const rows = useMemo(() => {
    const { choke, portFlags, topPorts } = sets;
    let list;
    if (filter === 'watching') list = [...choke, ...portFlags, ...topPorts].filter((e) => watched.has(e.id));
    else if (filter === 'critical') list = [...choke, ...portFlags].filter((e) => e.critical);
    else if (filter === 'chokepoints') list = choke;
    else if (filter === 'ports') list = [...portFlags, ...topPorts];
    else list = [...choke, ...portFlags];
    return [...list].sort(byCritThenSeverity);
  }, [sets, filter, watched]);

  // browser-notify on new/escalated flags for watched entities
  useEffect(() => { if (data) notifyWatched(watched, flags); }, [data, flags, watched]);

  const criticalCount = useMemo(
    () => [...sets.choke, ...sets.portFlags].filter((e) => e.critical).length,
    [sets]
  );

  const selectEntity = useCallback((e) => {
    setSelected(e);
    if (e && e.lat != null && mapApiRef.current) mapApiRef.current.flyTo(e.lon, e.lat);
  }, []);

  // brief bullet / stress gauge / search → jump to an entity by portid (fly globe
  // + open its row). Falls back to the full snapshot so ANY of the 2,065 ports works.
  const pickByPortid = useCallback((portid) => {
    const all = [...sets.choke, ...sets.portFlags, ...sets.topPorts];
    let e = all.find((x) => x.id === portid);
    if (!e && data) {
      const c = (data.snapshot?.chokepoints || []).find((x) => x.portid === portid);
      const p = c || (data.snapshot?.ports || []).find((x) => x.portid === portid);
      if (p) e = { id: p.portid, name: p.name, type: c ? 'chokepoint' : 'port',
        lat: p.lat, lon: p.lon, metric: c ? c.pct_change : null, flag: null, critical: false };
    }
    if (e) { setFilter('all'); selectEntity(e); }
  }, [sets, selectEntity, data]);

  const flagByPort = useMemo(() => {
    const m = {};
    (flags || []).filter((f) => f.lifecycle !== 'resolved').forEach((f) => { m[f.portid] = f; });
    return m;
  }, [flags]);

  // --- deep-link: selected entity + filter + scrub time <-> URL hash --------
  const appliedHash = useRef(false);
  useEffect(() => {
    if (!data || appliedHash.current) return;
    appliedHash.current = true;
    const h = new URLSearchParams(window.location.hash.slice(1));
    const e = h.get('e'); if (e) pickByPortid(e);         // sets filter='all' as a side effect…
    const f = h.get('f'); if (f) setFilter(f);            // …so restore the filter AFTER
    const t = h.get('t'); if (t !== null && t !== '') setScrubIndex(Number(t));
  }, [data, pickByPortid]);

  useEffect(() => {
    if (!data || !appliedHash.current) return;
    const p = new URLSearchParams();
    if (selected?.id) p.set('e', selected.id);
    if (filter !== 'all') p.set('f', filter);
    if (scrubIndex != null) p.set('t', String(scrubIndex));
    const s = p.toString();
    window.history.replaceState(null, '', s ? `#${s}` : window.location.pathname + window.location.search);
  }, [data, selected, filter, scrubIndex]);

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
          <StressGauge stress={data.stress} onOpen={() => setShowStress(true)} />
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
          {data && <Onboarding />}
        </section>

        {data && (
          <DataFeed
            rows={rows}
            filter={filter}
            setFilter={setFilter}
            criticalCount={criticalCount}
            exposure={exposureSummary}
            search={{ snapshot: data.snapshot, flagByPort, onJump: pickByPortid }}
            upload={{ flags: data.flags, applied: userExposure, onApply: setUserExposure, onReset: () => setUserExposure(null) }}
            brief={data.brief}
            flags={flags}
            disruptions={data.disruptions}
            gatun={data.gatun}
            scrubDate={scrubDate}
            scrubIndex={scrubIndex}
            onLive={() => { setPlaying(false); setScrubIndex(null); }}
            watched={watched}
            onToggleWatch={toggleWatch}
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

      {showStress && data?.stress && (
        <StressDetail stress={data.stress} onClose={() => setShowStress(false)} onPickEntity={pickByPortid} />
      )}

      {data && <Chat data={userExposure ? { ...data, flags, exposure: exposureSummary } : data} onPickEntity={pickByPortid} />}
    </div>
  );
}
