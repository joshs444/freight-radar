import { severityCss } from '../lib/colors.js';
import { Markdown } from '../lib/md.jsx';

const FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'critical', label: 'Critical' },
  { key: 'chokepoints', label: 'Chokepoints' },
  { key: 'ports', label: 'Ports' },
];

function Metric({ v, alert }) {
  if (v == null) return <span className="fr-metric fr-dim">—</span>;
  const up = v > 0;
  return (
    <span className={`fr-metric ${alert ? 'fr-hot' : ''}`}>
      {up ? '↑' : '↓'} {up ? '+' : ''}{Math.round(v)}%
    </span>
  );
}

function Row({ e, active, onSelect }) {
  return (
    <button
      className={`fr-row ${active ? 'is-active' : ''} ${e.critical ? 'is-critical' : ''}`}
      onClick={() => onSelect(active ? null : e)}
    >
      <div className="fr-row-main">
        {e.critical ? (
          <span className="fr-sev" style={{ color: severityCss(e.severity), borderColor: severityCss(e.severity) }}>
            {e.severity}
          </span>
        ) : (
          <span className="fr-rowdot" />
        )}
        <div className="fr-row-titles">
          <span className="fr-row-name">{e.name}</span>
          <span className="fr-row-sub">
            {e.type}{e.flag ? ` · ${e.flag.kind.replaceAll('_', ' ')}` : ' · normal'}
          </span>
        </div>
        <Metric v={e.metric} alert={e.critical} />
      </div>
      {active && e.flag && (
        <div className="fr-row-brief">
          <Markdown text={e.flag.brief_md} />
          <div className="fr-row-meta">
            <span>{e.flag.method}</span>
            <span>as of {e.flag.as_of}</span>
          </div>
        </div>
      )}
      {active && !e.flag && (
        <div className="fr-row-brief fr-row-stats">
          {e.n_total != null && (
            <span>{e.n_total} vessels/day · 28-day avg {e.baseline ?? '—'}</span>
          )}
          {e.vessels != null && <span>{e.vessels.toLocaleString()} vessels/yr</span>}
        </div>
      )}
    </button>
  );
}

export default function DataFeed({ rows, filter, setFilter, criticalCount, selected, onSelect, asOf, source }) {
  return (
    <aside className="fr-feed">
      <div className="fr-feed-head">
        <span className="fr-feed-title">Monitor</span>
        <span className="fr-feed-count">
          <b>{criticalCount}</b> critical · {rows.length} shown
        </span>
      </div>
      <div className="fr-filters">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            className={`fr-chip ${filter === f.key ? 'on' : ''}`}
            onClick={() => setFilter(f.key)}
          >
            {f.label}
          </button>
        ))}
      </div>
      <div className="fr-rows">
        {rows.length === 0 && <div className="fr-empty">Nothing to show in this filter.</div>}
        {rows.map((e) => (
          <Row key={e.id} e={e} active={selected?.id === e.id} onSelect={onSelect} />
        ))}
      </div>
      <div className="fr-feed-foot">
        <span>{source}</span>
        <span>as of <b>{asOf}</b></span>
      </div>
    </aside>
  );
}
