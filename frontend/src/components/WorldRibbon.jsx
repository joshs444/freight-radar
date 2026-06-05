import { Sparkline } from './Sparkline.jsx';
import { compact } from '../lib/format.js';

// World Today — a slim, always-visible pulse of global ocean freight under the top
// bar: how many ships are transiting, calling at ports, and how much cargo has been
// delivered / shipped — each with a today-vs-last-week trend and a 30-day sparkline.
// Real daily sums (world.json). Trend arrows are neutral: more activity isn't
// "good" or "bad", just up or down.
function Trend({ pct, dir, invert }) {
  if (pct == null) return null;
  const arrow = dir === 'up' ? '▲' : dir === 'down' ? '▼' : '▬';
  // color reflects good/bad, not just direction: for "disrupted", up is worse.
  const tone = invert ? (dir === 'up' ? 'down' : dir === 'down' ? 'up' : 'flat') : dir;
  return (
    <span className={`fr-w-trend ${tone}`}>
      {arrow} {pct > 0 ? '+' : ''}
      {pct}%<em>7d</em>
    </span>
  );
}

export default function WorldRibbon({ world }) {
  if (!world?.available || !world.metrics?.length) return null;
  return (
    <div className="fr-world" title={`Global ocean-freight activity · ${world.source}`}>
      <span className="fr-world-tag">World today</span>
      <div className="fr-world-tiles">
        {world.metrics.map((m) => (
          <div key={m.key} className="fr-w-tile">
            <div className="fr-w-meta">
              <span className="fr-w-label">{m.label}</span>
              <span className="fr-w-sub">{m.sublabel}</span>
            </div>
            <div className="fr-w-val">
              {compact(m.value)}
              <span className="fr-w-unit">{m.unit}</span>
            </div>
            <div className="fr-w-trendwrap">
              <Trend pct={m.vs7_pct} dir={m.trend} invert={m.invert} />
              <Sparkline values={m.spark} color="#8a93a3" width={54} height={18} />
            </div>
          </div>
        ))}
      </div>
      <span className="fr-world-asof">as of {world.as_of}</span>
    </div>
  );
}
