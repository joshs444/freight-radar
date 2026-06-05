import { useState } from 'react';
import { MdInline } from '../lib/md.tsx';
import { stressLevel } from '../lib/colors.ts';
import type { Brief } from '../types.ts';

// "What's moving in ocean freight" — a deterministic, fully-cited hero brief at the
// top of the feed. Numbers are computed in Python (brief.json); the prose is a
// template. Nothing here is model-generated, so nothing here can be hallucinated.
const DOT: Record<string, string> = {
  stress: '#c2611f',
  driver: '#c0392b',
  week: '#0d7d70',
  movers: '#b07b1e',
  market: '#0d9488',
  exposure: '#b07b1e',
};

interface BriefCardProps {
  brief: Brief | null;
  onPickEntity?: (portid: string) => void;
  onExport?: () => void;
}

export default function BriefCard({ brief, onPickEntity, onExport }: BriefCardProps) {
  // Default COLLAPSED so the brief doesn't steal the feed's height from the critical-issue
  // rows on first paint — the collapsed header still shows the kicker + the computed stress
  // headline, so it stays the always-on "what's going on" summary. Remembers if you open it.
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem('fr_brief_open') === '1';
    } catch {
      return false;
    }
  });
  const toggle = () =>
    setOpen((o) => {
      const next = !o;
      try {
        localStorage.setItem('fr_brief_open', next ? '1' : '0');
      } catch {
        /* ignore */
      }
      return next;
    });
  if (!brief?.bullets?.length) return null;
  const lv = stressLevel(brief.stress_label);

  return (
    <section className="fr-brief-card" style={{ borderColor: lv.edge }}>
      <div className="fr-brief-top" style={{ background: lv.tint }}>
        <button
          type="button"
          className="fr-brief-toggle-btn"
          onClick={toggle}
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
                      onClick={() => b.portid && onPickEntity?.(b.portid)}
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
