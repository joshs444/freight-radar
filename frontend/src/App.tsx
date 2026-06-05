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
const HistoryTimeline = lazy(() => import('./components/HistoryTimeline.tsx'));
import StormIndicator from './components/StormIndicator.tsx';
import Onboarding from './components/Onboarding.tsx';
import { useData } from './lib/useData.ts';
import { useWatchlist, notifyWatched } from './lib/useWatchlist.ts';
import { useMonitorModel } from './lib/useMonitorModel.ts';
import { useHistory } from './lib/useHistory.ts';
import type { MonitorEntity, MapApi, Flag, GlobeFlag, LayerId, LayerVisibility } from './types.ts';
import LayerPanel from './components/LayerPanel.tsx';
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
  // which globe overlays are visible — a real layer-control map (the LayerPanel), migrating
  // the old single fr_wind_off flag. Persisted so the choice sticks.
  const [layers, setLayers] = useState<LayerVisibility>(() => {
    const def: LayerVisibility = {
      flags: true,
      chokepoints: true,
      ports: true,
      ships: true,
      storms: true,
      lanes: true,
      wind: true,
    };
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

  // cross-highlight: a hovered feed row and/or a multi-field search light their marks on
  // the globe (a cyan ring). The Globe gets the union of both.
  const [hoveredId, setHoveredId] = useState<string | null>(null);
  const [searchHits, setSearchHits] = useState<string[]>([]);
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
            <span
              className="fr-provenance"
              title="Every figure is computed in Python from IMF PortWatch and string-substituted into template prose — no model is in the number path."
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
                  snapshot={hist.mode ? hist.snapshot : globeView.snapshot}
                  lanes={hist.mode ? [] : data.lanes}
                  flags={hist.mode ? hist.flags : globeView.flags}
                  ships={hist.mode ? null : data.ships}
                  storms={hist.mode ? [] : data.weather?.storms}
                  selectedFlag={hist.mode ? null : selected?.flag || null}
                  onSelectFlag={hist.mode ? noop : onSelectFlagFromGlobe}
                  mapApiRef={mapApiRef}
                  windOn={hist.mode ? false : layers.wind}
                  layers={layers}
                  highlightIds={hist.mode ? [] : highlightIds}
                />
              </Suspense>
            </ErrorBoundary>
          )}
          {data && !hist.mode && (
            <button className="fr-history-enter" onClick={hist.enter}>
              ▸ History · play 2019→now
            </button>
          )}
          {!hist.mode && data && (
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
              }}
              ships={data.ships ?? null}
              shipCoverage={shipCoverage}
              hasWind={!!data.wind}
            />
          )}
          {hist.mode && hist.event && (
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
          {hist.mode && hist.history ? (
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
          {data && !hist.mode && <Onboarding />}
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
