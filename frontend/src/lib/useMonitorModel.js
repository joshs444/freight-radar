import { useCallback, useMemo } from 'react';

// The "monitor model": everything that turns the raw sidecars (snapshot + flags +
// timeseries) into the entity universe the feed and the globe render. Extracted from
// App so the component is a thin orchestrator of state + layout, and this derivation
// — the genuinely intricate part — lives in one testable place.
//
// Inputs are the raw data + the current view state (filter, scrub position, watchlist)
// plus the two App-owned actions it needs to drive (selectEntity, setFilter). It
// returns the derived collections the UI consumes.

// critical first (by severity), then normal by real traffic — not by noisy %
const byCritThenSeverity = (a, b) =>
  b.critical - a.critical ||
  (b.severity || 0) - (a.severity || 0) ||
  (b.weight || 0) - (a.weight || 0);

export function useMonitorModel({
  data,
  flags,
  ts,
  filter,
  scrubIndex,
  watched,
  selectEntity,
  setFilter,
}) {
  // when scrubbing, the feed reflects that past day: only flags that had fired by
  // then are "active", and chokepoint metrics come from the history at that date.
  const scrubDate = scrubIndex != null && ts ? ts.dates[scrubIndex] : null;

  // --- the monitor universe: chokepoints + flagged ports + top ports ------
  const sets = useMemo(() => {
    if (!data) return { choke: [], portFlags: [], topPorts: [] };
    const flagByPort = {};
    (flags || [])
      .filter((f) => f.lifecycle !== 'resolved' && (!scrubDate || f.as_of <= scrubDate))
      .forEach((f) => {
        flagByPort[f.portid] = f;
      });
    const seriesAt = (portid, baseline) => {
      const v = ts?.series?.[portid]?.values?.[scrubIndex];
      if (v == null || !baseline) return null;
      return Math.round(((v - baseline) / baseline) * 1000) / 10;
    };

    // cargo_mix lookup so flagged-port rows (built from flags, not snapshot) can
    // still show the vessel mix from their snapshot record.
    const mixByPort = {};
    (data.snapshot?.chokepoints || []).forEach((c) => {
      if (c.cargo_mix) mixByPort[c.portid] = c.cargo_mix;
    });
    (data.snapshot?.ports || []).forEach((p) => {
      if (p.cargo_mix) mixByPort[p.portid] = p.cargo_mix;
    });
    // national-dependence lookup (ports only) for flagged-port rows built from flags
    const portMetaById = {};
    (data.snapshot?.ports || []).forEach((p) => {
      portMetaById[p.portid] = p;
    });

    const choke = (data.snapshot?.chokepoints || []).map((c) => {
      const flag = flagByPort[c.portid] || null;
      return {
        id: c.portid,
        name: c.name,
        type: 'chokepoint',
        lat: c.lat,
        lon: c.lon,
        // flagged rows show the flag's own pct (e.g. Hormuz -92% persistent), not
        // the noisy latest-vs-28d snapshot value (+124%); normals show the snapshot.
        // while scrubbing, normals show the value at the scrubbed date.
        metric: flag ? flag.pct_change : scrubDate ? seriesAt(c.portid, c.baseline) : c.pct_change,
        n_total: c.n_total,
        baseline: c.baseline,
        cargo_mix: c.cargo_mix,
        avg_vessel_size_dwt: c.avg_vessel_size_dwt,
        capacity_total: c.capacity_total,
        flag,
        severity: flag ? flag.severity : null,
        critical: !!flag,
        weight: c.n_total || 0,
      };
    });
    const chokeIds = new Set(choke.map((c) => c.id));
    const portFlags = Object.values(flagByPort)
      .filter((f) => !chokeIds.has(f.portid))
      .map((f) => ({
        id: f.portid,
        name: f.entity,
        type: 'port',
        lat: f.lat,
        lon: f.lon,
        metric: f.pct_change,
        flag: f,
        severity: f.severity,
        critical: true,
        weight: 1e9,
        cargo_mix: mixByPort[f.portid] || null,
        share_import: portMetaById[f.portid]?.share_import,
        share_export: portMetaById[f.portid]?.share_export,
        country: portMetaById[f.portid]?.country,
      }));
    const topPorts = [...(data.snapshot?.ports || [])]
      .sort((a, b) => b.vessels - a.vessels)
      .slice(0, 40)
      .filter((p) => !flagByPort[p.portid])
      .map((p) => ({
        id: p.portid,
        name: p.name,
        type: 'port',
        lat: p.lat,
        lon: p.lon,
        metric: null,
        vessels: p.vessels,
        flag: null,
        critical: false,
        weight: p.vessels || 0,
        cargo_mix: p.cargo_mix,
        share_import: p.share_import,
        share_export: p.share_export,
        country: p.country,
      }));
    return { choke, portFlags, topPorts };
  }, [data, flags, scrubDate, scrubIndex, ts]);

  const rows = useMemo(() => {
    const { choke, portFlags, topPorts } = sets;
    let list;
    if (filter === 'watching')
      list = [...choke, ...portFlags, ...topPorts].filter((e) => watched.has(e.id));
    else if (filter === 'critical') list = [...choke, ...portFlags].filter((e) => e.critical);
    else if (filter === 'chokepoints') list = choke;
    else if (filter === 'ports') list = [...portFlags, ...topPorts];
    else list = [...choke, ...portFlags];
    return [...list].sort(byCritThenSeverity);
  }, [sets, filter, watched]);

  const criticalCount = useMemo(
    () => [...sets.choke, ...sets.portFlags].filter((e) => e.critical).length,
    [sets]
  );

  // brief bullet / stress gauge / search → jump to an entity by portid (fly globe
  // + open its row). Falls back to the full snapshot so ANY of the 2,065 ports works.
  const pickByPortid = useCallback(
    (portid) => {
      const all = [...sets.choke, ...sets.portFlags, ...sets.topPorts];
      let e = all.find((x) => x.id === portid);
      if (!e && data) {
        const c = (data.snapshot?.chokepoints || []).find((x) => x.portid === portid);
        const p = c || (data.snapshot?.ports || []).find((x) => x.portid === portid);
        if (p)
          e = {
            id: p.portid,
            name: p.name,
            type: c ? 'chokepoint' : 'port',
            lat: p.lat,
            lon: p.lon,
            metric: c ? c.pct_change : null,
            flag: null,
            critical: false,
            cargo_mix: p.cargo_mix,
            share_import: p.share_import,
            share_export: p.share_export,
            country: p.country,
          };
      }
      if (e) {
        setFilter('all');
        selectEntity(e);
      }
    },
    [sets, selectEntity, data, setFilter]
  );

  const flagByPort = useMemo(() => {
    const m = {};
    (flags || [])
      .filter((f) => f.lifecycle !== 'resolved')
      .forEach((f) => {
        m[f.portid] = f;
      });
    return m;
  }, [flags]);

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
      portid: c.portid,
      name: c.name,
      lat: c.lat,
      lon: c.lon,
      n_total: c.values[scrubIndex],
      pct_change: null,
    }));
    return {
      snapshot: { ...data.snapshot, chokepoints },
      flags: ts.flags.filter((f) => f.as_of <= day),
    };
  }, [data, ts, scrubIndex]);

  return { scrubDate, rows, criticalCount, pickByPortid, flagByPort, globeView };
}
