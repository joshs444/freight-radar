import { useRef, useState, useCallback, useEffect, useMemo, lazy, Suspense } from 'react';
import DataFeed from './components/DataFeed.tsx';
import TimeScrubber from './components/TimeScrubber.tsx';
import StressGauge from './components/StressGauge.tsx';
import WorldRibbon from './components/WorldRibbon.tsx';
import ErrorBoundary from './components/ErrorBoundary.tsx';

// Heavy / interaction-gated views are lazy so the boot bundle is just the app shell:
// Globe pulls maplibre + deck + weatherlayers (~480KB gz); Chat pulls the in-browser
// query engine; StressDetail is modal-gated. React paints the shell while they stream in.
const Globe = lazy(() => import('./Globe.tsx'));
const Chat = lazy(() => import('./components/Chat.tsx'));
const StressDetail = lazy(() => import('./components/StressDetail.tsx'));
import StormIndicator from './components/StormIndicator.tsx';
import Onboarding from './components/Onboarding.tsx';
import { useData } from './lib/useData.ts';
import { useWatchlist, notifyWatched } from './lib/useWatchlist.ts';
import { useMonitorModel } from './lib/useMonitorModel.ts';
import type { MonitorEntity, MapApi, Flag, GlobeFlag } from './types.ts';
import type { AppliedExposure } from './components/Upload.tsx';

export default function App() {
  const { loading, error, data } = useData();
  const [selected, setSelected] = useState<MonitorEntity | null>(null);
  const [filter, setFilter] = useState('all');
  const [scrubIndex, setScrubIndex] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [userExposure, setUserExposure] = useState<AppliedExposure | null>(null);
  const [showStress, setShowStress] = useState(false);
  // ambient wind layer: on by default, but a toggle (the legend chip) lets you mute it
  // since it can read as busy; the choice is remembered.
  const [windOn, setWindOn] = useState(() => {
    try {
      return localStorage.getItem('fr_wind_off') !== '1';
    } catch {
      return true;
    }
  });
  const toggleWind = useCallback(() => {
    setWindOn((on) => {
      try {
        localStorage.setItem('fr_wind_off', on ? '1' : '0');
      } catch {
        /* ignore */
      }
      return !on;
    });
  }, []);
  const { watched, toggle: toggleWatch } = useWatchlist();
  const mapApiRef = useRef<MapApi | null>(null);

  const ts = data?.timeseries;

  // uploaded trade data (if any) overrides the sample exposure + per-flag business
  // (the `?? []` / `?? null` only bite before data loads, when nothing renders).
  // Memoised so the globe's data effect + callbacks keep stable deps across renders.
  const flags: Flag[] = useMemo(
    () => userExposure?.flags ?? data?.flags ?? [],
    [userExposure, data]
  );
  const exposureSummary = userExposure?.summary ?? data?.exposure ?? null;

  const selectEntity = useCallback((e: MonitorEntity | null) => {
    setSelected(e);
    if (e && e.lat != null && mapApiRef.current) mapApiRef.current.flyTo(e.lon, e.lat);
  }, []);

  // the derived monitor model: the entity universe, the filtered/sorted rows, the
  // critical count, the scrub-aware globe view, the search→entity lookup, and the
  // deep-link picker. All the intricate derivation lives in this one hook.
  const { scrubDate, rows, criticalCount, pickByPortid, flagByPort, globeView } = useMonitorModel({
    data,
    flags,
    ts,
    filter,
    scrubIndex,
    watched,
    selectEntity,
    setFilter,
  });

  // browser-notify on new/escalated flags for watched entities
  useEffect(() => {
    if (data) notifyWatched(watched, flags);
  }, [data, flags, watched]);

  // a flag ring clicked on the globe -> select the matching feed entity. The globe
  // flag may be a reduced scrub-replay flag, so resolve the full Flag by id (found when
  // it's a live disruption; null for a historical one — only the id is needed for the
  // ring highlight, and the row detail reads the full flag list itself).
  const onSelectFlagFromGlobe = useCallback(
    (flag: GlobeFlag) => {
      const full = flags.find((f) => f.flag_id === flag.flag_id) ?? null;
      selectEntity({
        id: flag.portid,
        name: flag.entity,
        type: flag.kind.startsWith('chokepoint') ? 'chokepoint' : 'port',
        lat: flag.lat,
        lon: flag.lon,
        metric: flag.pct_change ?? null,
        flag: full,
        severity: flag.severity,
        critical: true,
      });
    },
    [selectEntity, flags]
  );

  // --- deep-link: selected entity + filter + scrub time <-> URL hash --------
  const appliedHash = useRef(false);
  useEffect(() => {
    if (!data || appliedHash.current) return;
    appliedHash.current = true;
    const h = new URLSearchParams(window.location.hash.slice(1));
    const e = h.get('e');
    if (e) pickByPortid(e); // sets filter='all' as a side effect…
    const f = h.get('f');
    if (f) setFilter(f); // …so restore the filter AFTER
    const t = h.get('t');
    if (t !== null && t !== '') setScrubIndex(Number(t));
  }, [data, pickByPortid]);

  useEffect(() => {
    if (!data || !appliedHash.current) return;
    const p = new URLSearchParams();
    if (selected?.id) p.set('e', selected.id);
    if (filter !== 'all') p.set('f', filter);
    if (scrubIndex != null) p.set('t', String(scrubIndex));
    const s = p.toString();
    window.history.replaceState(
      null,
      '',
      s ? `#${s}` : window.location.pathname + window.location.search
    );
  }, [data, selected, filter, scrubIndex]);

  if (error) {
    return (
      <div className="fr-fallback">
        <h1>Freight Radar</h1>
        <p>Could not load the snapshot ({error}).</p>
        <p className="dim">
          Run the exporter: <code>python -m freight_radar.publish</code>
        </p>
      </div>
    );
  }

  const asOf = data?.snapshot?.as_of ?? '—';
  const source = data?.snapshot?.source ?? 'IMF PortWatch';

  return (
    <div className="fr-app">
      <a className="fr-skip" href="#fr-monitor">
        Skip to the monitor feed
      </a>
      <header className="fr-topbar">
        <div className="fr-brand">
          <span className="fr-logo" aria-hidden>
            ◐
          </span>
          <div>
            <h1>FREIGHT RADAR</h1>
            <p className="fr-tag">
              Ocean-freight chokepoints, monitored — disruptions auto-flagged from IMF PortWatch.
            </p>
          </div>
        </div>
        {data?.stress?.available && (
          <StressGauge stress={data.stress} onOpen={() => setShowStress(true)} />
        )}
        <StormIndicator
          storms={data?.weather?.storms}
          onPick={(s) => s?.lon != null && mapApiRef.current?.flyTo(s.lon, s.lat)}
        />
        <div className="fr-asof">
          <span className="fr-dot" /> {source}
          <br />
          data as of <b>{asOf}</b>
        </div>
      </header>

      {data?.world?.available && <WorldRibbon world={data.world} />}

      <div className="fr-main">
        <section className="fr-stage" aria-labelledby="fr-stage-label">
          <h2 id="fr-stage-label" className="sr-only">
            Interactive globe of ocean-freight chokepoints, ports, sampled vessel positions and
            wind. It is a visual aid — the Monitor feed has the same data and is fully
            keyboard-navigable.
          </h2>
          {data && (
            <ErrorBoundary
              fallback={
                <div className="fr-globe-fallback">
                  Map unavailable on this device — the feed, brief and chat still work.
                </div>
              }
            >
              <Suspense fallback={<div className="fr-globe-fallback">acquiring signal…</div>}>
                <Globe
                  snapshot={globeView.snapshot}
                  lanes={data.lanes}
                  flags={globeView.flags}
                  ships={data.ships}
                  storms={data.weather?.storms}
                  selectedFlag={selected?.flag || null}
                  onSelectFlag={onSelectFlagFromGlobe}
                  mapApiRef={mapApiRef}
                  windOn={windOn}
                />
              </Suspense>
            </ErrorBoundary>
          )}
          <div className="fr-legend">
            <span>
              <i className="sw amber" /> chokepoint
            </span>
            <span>
              <i className="sw port" /> port
            </span>
            <span>
              <i className="sw pulse" /> flagged
            </span>
            {data?.wind && (
              <button
                type="button"
                className={`fr-legend-toggle ${windOn ? 'on' : 'off'}`}
                onClick={toggleWind}
                aria-pressed={windOn}
                title={`${windOn ? 'Hide' : 'Show'} the animated wind · ${data.wind.source} · ${data.wind.cycle}`}
              >
                <i className="sw wind" /> wind{windOn ? '' : ' (off)'}
              </button>
            )}
            {(data?.weather?.counts?.active_storms ?? 0) > 0 && (
              <span>
                <i className="sw storm" /> storm
              </span>
            )}
            {data?.ships?.mode === 'live' && data?.ships?.count > 0 && (
              <span
                title={`Real AIS vessel positions near the chokepoints, sampled at last refresh · ${data.ships.count} vessels · aisstream.io`}
              >
                <i className="sw ship" /> {data.ships.count} ships · AIS
              </span>
            )}
          </div>
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
            upload={{
              flags: data.flags,
              applied: userExposure,
              onApply: setUserExposure,
              onReset: () => setUserExposure(null),
            }}
            brief={data.brief}
            flags={flags}
            disruptions={data.disruptions}
            gatun={data.gatun}
            scrubDate={scrubDate}
            scrubIndex={scrubIndex}
            onLive={() => {
              setPlaying(false);
              setScrubIndex(null);
            }}
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
        <Suspense fallback={null}>
          <StressDetail
            stress={data.stress}
            onClose={() => setShowStress(false)}
            onPickEntity={pickByPortid}
          />
        </Suspense>
      )}

      {data && (
        <Suspense fallback={null}>
          <Chat
            data={userExposure ? { ...data, flags, exposure: exposureSummary } : data}
            onPickEntity={pickByPortid}
          />
        </Suspense>
      )}
    </div>
  );
}
