import { useState } from 'react';
import { MdInline } from '../lib/md.jsx';
import { stressLevel } from '../lib/colors.js';

// "What's moving in ocean freight" — a deterministic, fully-cited hero brief at the
// top of the feed. Numbers are computed in Python (brief.json); the prose is a
// template. Nothing here is model-generated, so nothing here can be hallucinated.
const DOT = {
  stress: '#c2611f',
  driver: '#c0392b',
  week: '#0d7d70',
  movers: '#b07b1e',
  market: '#0d9488',
  exposure: '#b07b1e',
};

export default function BriefCard({ brief, onPickEntity, onExport }) {
  const [open, setOpen] = useState(true);
  if (!brief?.bullets?.length) return null;
  const lv = stressLevel(brief.stress_label);

  return (
    <section className="fr-brief-card" style={{ borderColor: lv.edge }}>
      <div className="fr-brief-top" style={{ background: lv.tint }}>
        <button
          type="button"
          className="fr-brief-toggle-btn"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          aria-label={open ? 'Collapse the weekly brief' : 'Expand the weekly brief'}
        >
          <div className="fr-brief-titles">
            <span className="fr-brief-kicker" style={{ color: lv.color }}>
              This week in ocean freight
            </span>
            <span className="fr-brief-headline">{brief.headline}</span>
          </div>
          <span className="fr-brief-toggle" aria-hidden="true">
            {open ? '–' : '+'}
          </span>
        </button>
        {onExport && (
          <button
            type="button"
            className="fr-brief-dl"
            onClick={onExport}
            aria-label="Download the weekly brief"
          >
            ↓
          </button>
        )}
      </div>
      {open && (
        <div className="fr-brief-body">
          <ul className="fr-brief-list">
            {brief.bullets.map((b, i) => {
              const linkable = b.portid && onPickEntity;
              const inner = (
                <>
                  <i
                    className="fr-brief-dot"
                    style={{ background: DOT[b.kind] || 'var(--ink-faint)' }}
                  />
                  <span className="fr-brief-text">
                    <MdInline text={b.text} />
                  </span>
                  {b.note && <span className="fr-brief-note">{b.note}</span>}
                </>
              );
              return (
                <li key={i} className="fr-brief-li">
                  {linkable ? (
                    <button
                      type="button"
                      className="fr-brief-li-inner is-link"
                      onClick={() => onPickEntity(b.portid)}
                    >
                      {inner}
                    </button>
                  ) : (
                    <div className="fr-brief-li-inner">{inner}</div>
                  )}
                </li>
              );
            })}
          </ul>
          <div className="fr-brief-foot">
            <span>{brief.source}</span>
            <span>
              as of <b>{brief.as_of}</b>
            </span>
          </div>
        </div>
      )}
    </section>
  );
}
