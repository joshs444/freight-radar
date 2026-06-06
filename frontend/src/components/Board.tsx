import { useMemo, useState } from 'react';
import type {
  MonitorEntity,
  Snapshot,
  Timeseries,
  Stress,
  NewsGeo,
  Quakes,
  Disruptions,
  Gatun,
  CargoMix,
} from '../types.ts';
import { Sparkline } from './Sparkline.tsx';
import { severityCss, stressLevel } from '../lib/colors.ts';
import SignalsRail from './SignalsRail.tsx';

// The Standpoint Board — the non-globe analytical view. A sphere can't be sorted; this is
// where you READ the data: rank the 28 measured chokepoints (+ flagged ports) by any
// computed column, line them up, scan the trend. It is a pure re-presentation of the SAME
// `rows` + sidecars the globe uses — zero new data, zero new compute — so every number is
// the same Python-computed, traceable value. The table is the MEASURED freight spine; the
// right rail is clearly-separated cited CONTEXT.

interface BoardProps {
  rows: MonitorEntity[];
  snapshot: Snapshot | null;
  timeseries: Timeseries | null;
  stress: Stress | null;
  newsGeo: NewsGeo | null;
  quakes: Quakes | null;
  disruptions: Disruptions | null;
  gatun: Gatun | null;
  asOf: string;
  source: string;
  selected: MonitorEntity | null;
  onPickEntity: (portid: string) => void;
  onHover: (id: string | null) => void;
  highlightIds: string[];
  watched: Set<string>;
  onToggleWatch: (id: string) => void;
}

type SortKey = 'sev' | 'name' | 'now' | 'norm' | 'pct' | 'z';

const num = (v: number | null | undefined): number =>
  v == null || Number.isNaN(v) ? Number.NEGATIVE_INFINITY : v;
const fmtPct = (v: number | null | undefined): string =>
  v == null ? '—' : `${v > 0 ? '+' : ''}${Math.round(v * 10) / 10}%`;
const fmtZ = (v: number | null | undefined): string => (v == null ? '—' : v.toFixed(1));
const fmtN = (v: number | null | undefined): string =>
  v == null ? '—' : Math.round(v).toLocaleString();

function CargoBar({ mix }: { mix: CargoMix | null | undefined }) {
  if (!mix) return null;
  const segs: [string, number, string][] = [
    ['container', mix.container, '#4f6da6'],
    ['tanker', mix.tanker, '#c9772f'],
    ['dry_bulk', mix.dry_bulk, '#7b8a5a'],
  ];
  return (
    <span className="fr-cargobar" aria-hidden>
      {segs.map(([k, v, c]) => (
        <i key={k} style={{ width: `${Math.round((v || 0) * 100)}%`, background: c }} />
      ))}
    </span>
  );
}

export default function Board({
  rows,
  snapshot,
  timeseries,
  stress,
  newsGeo,
  quakes,
  disruptions,
  gatun,
  asOf,
  source,
  selected,
  onPickEntity,
  onHover,
  highlightIds,
  watched,
  onToggleWatch,
}: BoardProps) {
  const [sortKey, setSortKey] = useState<SortKey>('sev');
  const [asc, setAsc] = useState(false);

  // z-score lookup: a flagged row carries its flag's z; an unflagged chokepoint reads the
  // snapshot's z. (Both are Python-computed in the same pipeline.)
  const zById = useMemo(() => {
    const m = new Map<string, number>();
    (snapshot?.chokepoints ?? []).forEach((c) => m.set(c.portid, c.zscore));
    return m;
  }, [snapshot]);
  const zFor = (e: MonitorEntity): number | null => e.flag?.zscore ?? zById.get(e.id) ?? null;

  const hi = useMemo(() => new Set(highlightIds), [highlightIds]);

  const sorted = useMemo(() => {
    const val = (e: MonitorEntity): number | string => {
      switch (sortKey) {
        case 'name':
          return e.name.toLowerCase();
        case 'now':
          return num(e.n_total);
        case 'norm':
          return num(e.baseline);
        case 'pct':
          return num(e.metric);
        case 'z':
          return num(zFor(e));
        default:
          return (e.critical ? 100 : 0) + num(e.severity ?? 0);
      }
    };
    const dir = asc ? 1 : -1;
    return [...rows].sort((a, b) => {
      const va = val(a);
      const vb = val(b);
      if (typeof va === 'string' || typeof vb === 'string')
        return String(va).localeCompare(String(vb)) * dir;
      return (va - vb) * dir;
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows, sortKey, asc, zById]);

  const onSort = (k: SortKey) => {
    if (k === sortKey) setAsc((a) => !a);
    else {
      setSortKey(k);
      setAsc(k === 'name'); // names default A→Z, numbers default high→low
    }
  };

  const sl = stress ? stressLevel(stress.label) : null;
  const cols: { key: SortKey; label: string; cls?: string }[] = [
    { key: 'sev', label: 'sev' },
    { key: 'name', label: 'chokepoint' },
    { key: 'now', label: 'now/d', cls: 'n' },
    { key: 'norm', label: 'norm', cls: 'n' },
    { key: 'pct', label: 'Δ%', cls: 'n' },
    { key: 'z', label: 'z', cls: 'n' },
  ];

  return (
    <div className="fr-board" aria-label="Standpoint board">
      {stress?.available && sl && (
        <div className="fr-board-stress">
          <span className="fr-bs-idx" style={{ color: sl.color }}>
            {Math.round(stress.index)}
            <small>/100</small>
          </span>
          <span className="fr-bs-label" style={{ color: sl.color }}>
            {stress.label}
          </span>
          <span className={`fr-bs-wow ${stress.wow_delta >= 0 ? 'up' : 'down'}`}>
            {stress.wow_delta >= 0 ? '▲' : '▼'}
            {Math.abs(Math.round(stress.wow_delta * 10) / 10)} vs last wk
          </span>
          <span className="fr-bs-bd">
            breadth {Math.round(stress.breadth)} · depth {Math.round(stress.depth)}
          </span>
          {stress.history?.length > 1 && (
            <Sparkline values={stress.history} width={120} height={22} color={sl.color} />
          )}
          <span className="fr-bs-meas">measured · freight spine · computed in Python</span>
        </div>
      )}

      <div className="fr-board-grid">
        <div className="fr-board-tablewrap">
          <table className="fr-chk-table">
            <thead>
              <tr>
                {cols.map((c) => (
                  <th
                    key={c.key}
                    className={`${c.cls || ''} ${sortKey === c.key ? 'sorted' : ''}`}
                    aria-sort={sortKey === c.key ? (asc ? 'ascending' : 'descending') : 'none'}
                  >
                    <button
                      type="button"
                      onClick={() => onSort(c.key)}
                      title={`Sort by ${c.label}`}
                    >
                      {c.label}
                      {sortKey === c.key ? (asc ? ' ▲' : ' ▼') : ' ⇅'}
                    </button>
                  </th>
                ))}
                <th className="t">trend · 120d</th>
                <th className="w" aria-label="watch" />
              </tr>
            </thead>
            <tbody>
              {sorted.map((e) => {
                const z = zFor(e);
                const sv = e.severity ?? null;
                const sparkVals = timeseries?.series?.[e.id]?.values;
                return (
                  <tr
                    key={e.id}
                    className={`${e.id === selected?.id ? 'sel' : ''} ${hi.has(e.id) ? 'hi' : ''} ${e.critical ? 'crit' : ''}`}
                    onClick={() => onPickEntity(e.id)}
                    onMouseEnter={() => onHover(e.id)}
                    onMouseLeave={() => onHover(null)}
                  >
                    <td className="sev">
                      <i
                        className="fr-sevdot"
                        style={{
                          background: sv != null ? severityCss(sv) : 'transparent',
                          borderColor: sv != null ? 'transparent' : 'var(--line-strong)',
                        }}
                        title={sv != null ? `severity ${sv}` : 'no flag'}
                      />
                      {sv != null ? Math.round(sv) : ''}
                    </td>
                    <td className="name">
                      <span className="fr-chk-name">{e.name}</span>
                      {e.country && <span className="fr-chk-country">{e.country}</span>}
                      <CargoBar mix={e.cargo_mix} />
                    </td>
                    <td className="n">{fmtN(e.n_total)}</td>
                    <td className="n dim">{fmtN(e.baseline)}</td>
                    <td
                      className={`n ${e.metric != null && e.metric < 0 ? 'neg' : e.metric != null && e.metric > 0 ? 'pos' : ''}`}
                    >
                      {fmtPct(e.metric)}
                    </td>
                    <td className={`n ${z != null && Math.abs(z) >= 2 ? 'hot' : ''}`}>{fmtZ(z)}</td>
                    <td className="t">
                      {sparkVals && sparkVals.length > 1 ? (
                        <Sparkline
                          values={sparkVals}
                          width={92}
                          height={18}
                          color={sv != null ? severityCss(sv) : '#9aa6bd'}
                        />
                      ) : (
                        <span className="fr-dim">—</span>
                      )}
                    </td>
                    <td className="w">
                      <button
                        type="button"
                        className={`fr-watch ${watched.has(e.id) ? 'on' : ''}`}
                        aria-pressed={watched.has(e.id)}
                        aria-label={watched.has(e.id) ? `Unwatch ${e.name}` : `Watch ${e.name}`}
                        onClick={(ev) => {
                          ev.stopPropagation();
                          onToggleWatch(e.id);
                        }}
                      >
                        ★
                      </button>
                    </td>
                  </tr>
                );
              })}
              {!sorted.length && (
                <tr>
                  <td colSpan={8} className="fr-board-empty">
                    No rows for this filter.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
          <p className="fr-board-foot">
            src {source} · as of <b>{asOf}</b> · every column computed in Python · click a row to
            open its cited brief
          </p>
        </div>

        <SignalsRail newsGeo={newsGeo} quakes={quakes} disruptions={disruptions} gatun={gatun} />
      </div>
    </div>
  );
}
