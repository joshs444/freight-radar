import { severityCss } from '../lib/colors.js';
import { Markdown } from '../lib/md.jsx';

const LIFECYCLE = {
  new: { label: 'NEW', cls: 'lc-new' },
  ongoing: { label: 'ONGOING', cls: 'lc-ongoing' },
  escalated: { label: 'ESCALATED ↑', cls: 'lc-esc' },
  resolved: { label: 'RESOLVED', cls: 'lc-resolved' },
};

// active issues first (by severity), resolved tombstones dimmed at the bottom
const order = (f) => (f.lifecycle === 'resolved' ? 1 : 0);

function FlagCard({ flag, active, onSelect }) {
  const accent = severityCss(flag.severity);
  const lc = LIFECYCLE[flag.lifecycle] || null;
  const resolved = flag.lifecycle === 'resolved';
  return (
    <button
      className={`fr-card ${active ? 'is-active' : ''} ${resolved ? 'is-resolved' : ''}`}
      style={{ '--accent': accent }}
      onClick={() => onSelect(active ? null : flag)}
    >
      <div className="fr-card-top">
        <span className="fr-sev" style={{ color: accent, borderColor: accent }}>
          {flag.severity}
        </span>
        <div className="fr-card-titles">
          <span className="fr-card-entity">{flag.entity}</span>
          <span className="fr-card-kind-row">{flag.kind.replaceAll('_', ' ')}</span>
        </div>
        {lc && <span className={`fr-lc ${lc.cls}`}>{lc.label}</span>}
      </div>
      <div className="fr-card-headline">{flag.headline}</div>
      {active && (
        <div className="fr-card-brief">
          <Markdown text={flag.brief_md} />
          <div className="fr-card-meta">
            <span>method · {flag.method}</span>
            <span>as of {flag.as_of}</span>
          </div>
        </div>
      )}
    </button>
  );
}

export default function IssuesRail({ flags, selectedFlag, onSelect, asOf, source }) {
  const all = [...(flags || [])].sort(
    (a, b) => order(a) - order(b) || b.severity - a.severity
  );
  const activeFlags = all.filter((f) => f.lifecycle !== 'resolved');
  const resolvedFlags = all.filter((f) => f.lifecycle === 'resolved').slice(0, 3);
  const ranked = [...activeFlags, ...resolvedFlags]; // recently-resolved capped at 3
  const active = activeFlags.length;
  return (
    <aside className="fr-rail">
      <header className="fr-rail-head">
        <div className="fr-rail-title">Current Issues</div>
        <div className="fr-rail-count">{active}</div>
      </header>
      <div className="fr-rail-sub">severity-ranked · auto-flagged</div>
      <div className="fr-rail-list">
        {ranked.length === 0 && <div className="fr-empty">No active disruptions detected.</div>}
        {ranked.map((f) => (
          <FlagCard
            key={f.flag_id}
            flag={f}
            active={selectedFlag?.flag_id === f.flag_id}
            onSelect={onSelect}
          />
        ))}
      </div>
      <footer className="fr-rail-foot">
        <div>{source}</div>
        <div>data as of <b>{asOf}</b></div>
      </footer>
    </aside>
  );
}
