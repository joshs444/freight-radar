import Trace from './Trace.tsx';
import type { ContextPick } from '../lib/sources.ts';

// Clicking a CONTEXT dot used to throw you straight off-site (window.open) — you'd never see "this
// is CONTEXT · USGS · public domain · association only" before leaving. This card makes the dot
// trace UP first: the cited reading as-published + the layer's tier/source/honesty-note (resolved
// from the registry catalog by layerId via <Trace>), THEN the explicit "open source ↗" deep link.
// Hover still shows the tooltip; a click opens this. A context dot says WHAT it is before it sends
// you away.

interface ContextTraceCardProps {
  pick: ContextPick | null;
  onClose: () => void;
}

export default function ContextTraceCard({ pick, onClose }: ContextTraceCardProps) {
  if (!pick) return null;
  return (
    <div className="fr-ctxcard" role="dialog" aria-label={`Source trace — ${pick.title}`}>
      <div className="fr-ctxcard-top">
        <span className="fr-ctxcard-title">{pick.title}</span>
        <button
          type="button"
          className="fr-ctxcard-close"
          onClick={onClose}
          aria-label="Close source trace"
        >
          ✕
        </button>
      </div>
      {/* Trace resolves tier (cited · context), the cited source link + license, and the layer's
          honesty-note from the catalog by layerId. raw = the reading exactly as the source states it. */}
      <Trace layerId={pick.layerId} raw={pick.value} asOf={pick.asOf} />
      {pick.url ? (
        <a className="fr-ctxcard-out" href={pick.url} target="_blank" rel="noopener noreferrer">
          open the cited report ↗
        </a>
      ) : (
        <span className="fr-ctxcard-nolink">
          no per-item link — see the file-level source above
        </span>
      )}
    </div>
  );
}
