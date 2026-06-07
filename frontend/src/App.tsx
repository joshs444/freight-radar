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
const Board = lazy(() => import('./components/Board.tsx'));
const StoreQuery = lazy(() => import('./components/StoreQuery.tsx'));
const SourceLedger = lazy(() => import('./components/SourceLedger.tsx'));
const Chat = lazy(() => import('./components/Chat.tsx'));
const StressDetail = lazy(() => import('./components/StressDetail.tsx'));
const HistoryTimeline = lazy(() => import('./components/HistoryTimeline.tsx'));
import StormIndicator from './components/StormIndicator.tsx';
import Onboarding from './components/Onboarding.tsx';
import ViewToggle from './components/ViewToggle.tsx';
import { useData } from './lib/useData.ts';
import { useWatchlist, notifyWatched } from './lib/useWatchlist.ts';
import { useMonitorModel } from './lib/useMonitorModel.ts';
import { useHistory } from './lib/useHistory.ts';
import type {
  MonitorEntity,
  MapApi,
  Flag,
  GlobeFlag,
  LayerId,
  LayerVisibility,
  AppView,
} from './types.ts';
import LayerPanel from './components/LayerPanel.tsx';
import { DEFAULT_LAYER_VISIBILITY } from './lib/layers.gen.ts';
import type { AppliedExposure } from './components/Upload.tsx';

// labels for the GFS wind forecast scrubber (matches backend wind.FHOURS = 0,24,48,72,96)
const WIND_FRAMES = ['now', '+1 day', '+2 days', '+3 days', '+4 days'];

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
  // which globe overlays are visible — a real layer-control map (the LayerPanel), migrating
  // the old single fr_wind_off flag. Persisted so the choice sticks.
  const [layers, setLayers] = useState<LayerVisibility>(() => {
    // Defaults come from the generated registry manifest (layers.gen.ts); copy so the
    // fr_wind_off migration below can mutate this instance without touching the const.
    const def: LayerVisibility = { ...DEFAULT_LAYER_VISIBILITY };
    try {
      const saved = localStorage.getItem('fr_layers');
      if (saved) return { ...def, ...(JSON.parse(saved) as Partial<LayerVisibility>) };
      if (localStorage.getItem('fr_wind_off') === '1') def.wind = false; // migrate old flag
    } catch {
      /* ignore */
    }
    return def;
  });
  const toggleLayer = useCallback((id: LayerId) => {
    setLayers((m) => {
      const next = { ...m, [id]: !m[id] };
      try {
        localStorage.setItem('fr_layers', JSON.stringify(next));
      } catch {
        /* ignore */
      }
      return next;
    });
  }, []);
  const { watched, toggle: toggleWatch } = useWatchlist();
  const mapApiRef = useRef<MapApi | null>(null);

  // globe (explore) vs board (scan/sort) vs data (in-browser SQL) — same store, three reads.
  // Persisted + deep-linked.
  const [view, setView] = useState<AppView>(() => {
    try {
      const fromHash = new URLSearchParams(window.location.hash.slice(1)).get('v');
      if (fromHash === 'board' || fromHash === 'data' || fromHash === 'ledger') return fromHash;
      const saved = localStorage.getItem('fr_view');
      if (saved === 'board' || saved === 'data' || saved === 'ledger') return saved;
    } catch {
      /* ignore */
    }
    return 'globe';
  });
  const changeView = useCallback((v: AppView) => {
    setView(v);
    try {
      localStorage.setItem('fr_view', v);
    } catch {
      /* ignore */
    }
  }, []);

  // cross-highlight: a hovered feed row and/or a multi-field search light their marks on
  // the globe (a cyan ring). The Globe gets the union of both.
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [searchHits, setSearchHits] = useState<string[]>([]);
  // GFS wind forecast scrubber: 0 = now (analysis) … 4 = +4 days
  const [windFrame, setWindFrame] = useState(0);
  const highlightIds = useMemo(
    () => (hoveredId ? [...new Set([hoveredId, ...searchHits])] : searchHits),
    [hoveredId, searchHits]
  );

  // honest ship coverage: how many of the 28 chokepoints actually have a sampled vessel
  // near them right now (the live sample clusters near a handful, not all 28) — the most
  // truthful answer to "do we see all the ships?".
  const shipCoverage = useMemo(() => {
    const v = data?.ships?.vessels ?? [];
    const ch = data?.snapshot?.chokepoints ?? [];
    if (!v.length || !ch.length) return 0;
    return ch.filter((c) =>
      v.some((s) => Math.abs(s.lat - c.lat) < 1.6 && Math.abs(s.lon - c.lon) < 1.6)
    ).length;
  }, [data]);

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

  // "play through history" (2019→now) — owns its own load/playhead state and derives the
  // synthetic globe view at the playhead week; the live view is untouched until entered.
  const hist = useHistory(data?.snapshot?.ports ?? []);
  const noop = useCallback(() => {}, []);

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
    if (view !== 'globe') p.set('v', view);
    const s = p.toString();
    window.history.replaceState(
      null,
      '',
      s ? `#${s}` : window.location.pathname + window.location.search
    );
  }, [data, selected, filter, scrubIndex, view]);

  if (error) {
    return (
      <div className="fr-fallback">
        <h1>Standpoint</h1>
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
            <h1>STANDPOINT</h1>
            <p className="fr-tag">
              Real, cited world signals on one globe — freight throughput is the measured spine;
              everything else is possibly-related context.
            </p>
            <span
              className="fr-provenance"
              title="Every figure is computed in Python from IMF PortWatch and string-substituted into template prose — no model is in the number path. Context layers (weather, news, hazards) are cited public data, never a stated cause and never a forecast of freight."
            >
              Computed in Python · IMF PortWatch · no model in the number path
            </span>
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

      {data?.brief?.headline && (
        <div className="fr-lede" role="status">
          <span className="fr-lede-dot" />
          <span className="fr-lede-text">{data.brief.headline}</span>
          <span className="fr-lede-tag">this week</span>
        </div>
      )}

      <div className="fr-main">
        <section className="fr-stage" aria-labelledby="fr-stage-label">
          <h2 id="fr-stage-label" className="sr-only">
            Interactive globe of ocean-freight chokepoints, ports, sampled vessel positions and
            wind. It is a visual aid — the Monitor feed has the same data and is fully
            keyboard-navigable.
          </h2>
          {data && <ViewToggle view={view} onChange={changeView} />}
          {view === 'board' && data && (
            <Suspense fallback={<div className="fr-globe-fallback">building the board…</div>}>
              <Board
                rows={rows}
                snapshot={data.snapshot}
                timeseries={data.timeseries}
                stress={data.stress}
                newsGeo={data.newsGeo}
                quakes={data.quakes}
                disruptions={data.disruptions}
                gatun={data.gatun}
                asOf={asOf}
                source={source}
                selected={selected}
                onPickEntity={pickByPortid}
                onHover={setHoveredId}
                highlightIds={highlightIds}
                watched={watched}
                onToggleWatch={toggleWatch}
              />
            </Suspense>
          )}
          {view === 'data' && data && (
            <Suspense fallback={<div className="fr-globe-fallback">loading the SQL engine…</div>}>
              <StoreQuery />
            </Suspense>
          )}
          {view === 'ledger' && data && (
            <Suspense
              fallback={<div className="fr-globe-fallback">loading the source ledger…</div>}
            >
              <SourceLedger />
            </Suspense>
          )}
          {view === 'globe' && data && (
            <ErrorBoundary
              fallback={
                <div className="fr-globe-fallback">
                  Map unavailable on this device — the feed, brief and chat still work.
                </div>
              }
            >
              <Suspense fallback={<div className="fr-globe-fallback">acquiring signal…</div>}>
                <Globe
                  snapshot={hist.mode ? hist.snapshot : globeView.snapshot}
                  lanes={hist.mode ? [] : data.lanes}
                  flags={hist.mode ? hist.flags : globeView.flags}
                  ships={hist.mode ? null : data.ships}
                  storms={hist.mode ? [] : data.weather?.storms}
                  newsDots={hist.mode ? [] : (data.newsGeo?.items ?? [])}
                  quakeDots={hist.mode ? [] : (data.quakes?.items ?? [])}
                  eonetDots={hist.mode ? [] : (data.eonet?.items ?? [])}
                  selectedFlag={hist.mode ? null : selected?.flag || null}
                  onSelectFlag={hist.mode ? noop : onSelectFlagFromGlobe}
                  mapApiRef={mapApiRef}
                  windOn={hist.mode ? false : layers.wind}
                  windFrame={windFrame}
                  layers={layers}
                  highlightIds={hist.mode ? [] : highlightIds}
                />
              </Suspense>
            </ErrorBoundary>
          )}
          {view === 'globe' && data && !hist.mode && (
            <button className="fr-history-enter" onClick={hist.enter}>
              ▸ History · play 2019→now
            </button>
          )}
          {view === 'globe' && !hist.mode && data && (
            <LayerPanel
              layers={layers}
              onToggle={toggleLayer}
              counts={{
                flags: flags.length,
                chokepoints: data.snapshot?.chokepoints?.length ?? 0,
                ports: data.snapshot?.ports?.length ?? 0,
                ships: data.ships?.count ?? 0,
                storms: data.weather?.counts?.active_storms ?? 0,
                lanes: data.lanes?.length ?? 0,
                news: data.newsGeo?.items?.length ?? 0,
                quakes: data.quakes?.items?.length ?? 0,
                eonet: data.eonet?.items?.length ?? 0,
              }}
              ships={data.ships ?? null}
              shipCoverage={shipCoverage}
              hasWind={!!data.wind}
              newsGeo={data.newsGeo ?? null}
              quakes={data.quakes ?? null}
              spineFdr={{
                tested: data.snapshot?.ports?.length ?? 0,
                flagged: flags.filter((f) => String(f.portid).startsWith('port')).length,
              }}
            />
          )}
          {view === 'globe' && !hist.mode && data?.wind && layers.wind && (
            <div className="fr-wind-scrub" role="group" aria-label="GFS wind forecast hour">
              <span className="fr-wind-scrub-lbl">GFS wind forecast</span>
              <input
                className="fr-wind-scrub-range"
                type="range"
                min={0}
                max={WIND_FRAMES.length - 1}
                value={windFrame}
                onChange={(e) => setWindFrame(Number(e.target.value))}
                aria-label="Scrub the NOAA GFS wind forecast forward in time"
              />
              <span className="fr-wind-scrub-val">{WIND_FRAMES[windFrame]}</span>
            </div>
          )}
          {view === 'globe' && hist.mode && hist.event && (
            <div className="fr-hist-caption" role="status">
              <div className="fr-hist-caption-title">{hist.event.title}</div>
              <p className="fr-hist-caption-blurb">{hist.event.blurb}</p>
              <a
                className="fr-hist-caption-src"
                href={hist.event.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {hist.event.source} ↗
              </a>
            </div>
          )}
          {view === 'globe' && hist.mode && hist.history ? (
            <Suspense fallback={null}>
              <HistoryTimeline
                history={hist.history}
                week={hist.week}
                playing={hist.playing}
                onWeek={hist.setWeek}
                onPlayToggle={hist.togglePlay}
                onClose={hist.exit}
              />
            </Suspense>
          ) : (
            ts &&
            ts.dates?.length > 1 && (
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
            )
          )}
          {loading && <div className="fr-loading">acquiring signal…</div>}
          {view === 'globe' && data && !hist.mode && <Onboarding />}
        </section>

        {data && (
          <DataFeed
            rows={rows}
            filter={filter}
            setFilter={setFilter}
            criticalCount={criticalCount}
            exposure={exposureSummary}
            search={{
              snapshot: data.snapshot,
              flagByPort,
              onJump: pickByPortid,
              onResults: setSearchHits,
            }}
            onHover={setHoveredId}
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
