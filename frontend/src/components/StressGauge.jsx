import { Sparkline } from './Sparkline.jsx';
import { stressLevel } from '../lib/colors.js';

// The at-a-glance number: Global Ocean Freight Stress (0-100), in the top bar.
// Index + level + week-over-week momentum + a 30-day sparkline. Clicking it opens
// the "what's moving" brief. Every value comes straight from stress.json.
export default function StressGauge({ stress, onOpen }) {
  if (!stress?.available) return null;
  const lv = stressLevel(stress.label);
  const wow = stress.wow_delta || 0;
  const dir = stress.wow_direction;
  const arrow = dir === 'up' ? '▲' : dir === 'down' ? '▼' : '▬';
  const pct = Math.max(2, Math.min(100, stress.index));

  return (
    <button
      className="fr-stress"
      onClick={onOpen}
      title={`${stress.method}\nbreadth ${stress.breadth} · depth ${stress.depth} · ${stress.source}`}
    >
      <div className="fr-stress-left">
        <span className="fr-stress-label">Ocean Freight Stress <span className="fr-stress-info">ⓘ what's this</span></span>
        <span className="fr-stress-sub">
          {stress.chokepoints_disrupted}/{stress.chokepoints_total} chokepoints disrupted
        </span>
        <div className="fr-stress-bar"><i style={{ width: `${pct}%`, background: lv.color }} /></div>
      </div>
      <div className="fr-stress-num" style={{ color: lv.color }}>
        {stress.index}<span className="fr-stress-max">/100</span>
      </div>
      <span className="fr-stress-badge" style={{ color: lv.color, background: lv.tint, borderColor: lv.edge }}>
        {stress.label}
      </span>
      <span className="fr-stress-wow" style={{ color: dir === 'up' ? '#c0392b' : dir === 'down' ? '#0d9488' : 'var(--ink-faint)' }}>
        {arrow} {wow > 0 ? '+' : ''}{wow}
        <em>wk</em>
      </span>
      <span className="fr-stress-spark"><Sparkline values={stress.spark30} color={lv.color} width={76} height={24} /></span>
    </button>
  );
}
