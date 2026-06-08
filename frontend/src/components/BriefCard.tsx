import { useState } from 'react';
import { MdInline } from '../lib/md.tsx';
import { stressLevel } from '../lib/colors.ts';
import { useCatalog, effectiveSource } from '../lib/catalog.ts';
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

// Each brief bullet already carries `cites` (the sidecar stems it was computed from) — the brief is
// the surface a casual user actually reads, yet it was the LEAST-traced (P1-D). Render the cites as
// small chips that link to the cited source, resolved through the same registry catalog every Trace
// reads. Rendered OUTSIDE the bullet's click target — an <a> inside a <button> is invalid nesting.
function CiteChips({ cites }: { cites: string[] }) {
  const catalog = useCatalog();
  if (!cites?.length) return null;
  return (
    <span className="fr-brief-cites">
      {cites.map((cite) => {
        const stem = cite.replace(/\.json$/, '');
        const eff = effectiveSource(catalog, stem);
        const url = eff.source?.url ?? null;
        return url ? (
          <a
            key={cite}
            className="fr-brief-cite is-link"
            href={url}
            target="_blank"
            rel="noopener noreferrer"
            title={eff.source?.name ? `cited from ${eff.source.name}` : undefined}
          >
            {stem} ↗
          </a>
        ) : (
          <code key={cite} className="fr-brief-cite">
            {stem}
          </code>
        );
      })}
    </span>
  );
}

export default function BriefCard({ brief, onPickEntity, onExport }: BriefCardProps) {
  // Default OPEN — the brief IS the answer to "what's happening", so it leads. (It used to
  // default collapsed to protect the feed's height, but the feed now defaults to ~signal-only
  // rows, so there's room for both.) Respect an explicit user collapse ('0') across visits.
  const [open, setOpen] = useState(() => {
    try {
      return localStorage.getItem('fr_brief_open') !== '0';
    } catch {
      return true;
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
                  <CiteChips cites={b.cites} />
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
