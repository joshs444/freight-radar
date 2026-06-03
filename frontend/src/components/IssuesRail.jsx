import { severityCss } from '../lib/colors.js';
import { Markdown } from '../lib/md.jsx';

function SeverityBadge({ s }) {
  return (
    <span className="fr-sev" style={{ color: severityCss(s), borderColor: severityCss(s) }}>
      {s}
    </span>
  );
}

function FlagCard({ flag, active, onSelect }) {
  const accent = severityCss(flag.severity);
  return (
    <button
      className={`fr-card ${active ? 'is-active' : ''}`}
      style={{ '--accent': accent }}
      onClick={() => onSelect(active ? null : flag)}
    >
      <div className="fr-card-top">
        <SeverityBadge s={flag.severity} />
        <span className="fr-card-entity">{flag.entity}</span>
        <span className="fr-card-kind">{flag.kind.replaceAll('_', ' ')}</span>
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
  const ranked = [...(flags || [])].sort((a, b) => b.severity - a.severity);
  return (
    <aside className="fr-rail">
      <header className="fr-rail-head">
        <div className="fr-rail-title">Current Issues</div>
        <div className="fr-rail-count">{ranked.length}</div>
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
