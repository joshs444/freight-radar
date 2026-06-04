import { stressLevel } from '../lib/colors.js';
import { Sparkline } from './Sparkline.jsx';

// Click-to-explain panel for the Ocean Freight Stress Index. The whole point is
// transparency: say plainly what the score is (our composite, not an official
// index), how it's scored, and exactly why it's at this value right now — every
// figure read straight from stress.json.
const SCALE = [
  { label: 'calm', range: '0–15' },
  { label: 'elevated', range: '15–35' },
  { label: 'high', range: '35–55' },
  { label: 'severe', range: '55–100' },
];

export default function StressDetail({ stress, onClose, onPickEntity }) {
  if (!stress?.available) return null;
  const lv = stressLevel(stress.label);
  const wow = stress.wow_delta || 0;
  const dirWord = stress.wow_direction === 'up' ? 'up' : stress.wow_direction === 'down' ? 'down' : 'flat';
  const contribs = stress.contributors || [];
  const maxC = Math.max(...contribs.map((c) => c.contribution), 0.01);

  return (
    <div className="fr-sd-backdrop" onClick={onClose}>
      <div className="fr-sd" onClick={(e) => e.stopPropagation()} role="dialog">
        <button className="fr-sd-x" onClick={onClose} aria-label="close">×</button>

        <div className="fr-sd-head">
          <div>
            <div className="fr-sd-kicker">Ocean Freight Stress Index</div>
            <div className="fr-sd-score" style={{ color: lv.color }}>
              {stress.index}<span>/100</span>
              <em style={{ color: lv.color, background: lv.tint, borderColor: lv.edge }}>{stress.label}</em>
            </div>
            <div className="fr-sd-wow">{dirWord === 'flat' ? 'flat' : `${dirWord} ${Math.abs(wow)} pts`} vs last week</div>
          </div>
          <div className="fr-sd-spark">
            <Sparkline values={(stress.history || []).slice(-90)} width={170} height={46} color={lv.color} strokeWidth={1.6} />
            <span>last 90 days</span>
          </div>
        </div>

        <p className="fr-sd-what">
          A single 0–100 score we compute from IMF PortWatch vessel data to summarise how disrupted global
          ocean freight is right now versus normal. It's <b>our own composite — not an official index</b>, and it's
          fully transparent. Here's exactly what goes into it.
        </p>

        <div className="fr-sd-grid">
          <div className="fr-sd-comp">
            <div className="fr-sd-comp-h">Breadth <b>{stress.breadth}</b></div>
            <p>How broadly the network is stressed — an economic-weighted average of every chokepoint's deviation
              from its own normal throughput. <b>{stress.chokepoints_disrupted} of {stress.chokepoints_total}</b> are
              disrupted right now.</p>
          </div>
          <div className="fr-sd-comp">
            <div className="fr-sd-comp-h">Depth <b>{stress.depth}</b></div>
            <p>How bad the single <i>worst</i> chokepoint is. Blended in at 40% on purpose, so a crisis at one
              strategic strait (a Suez or a Hormuz) isn't averaged away by 27 calm ones.</p>
          </div>
        </div>
        <div className="fr-sd-formula">
          index = 0.6 × breadth + 0.4 × depth = <b style={{ color: lv.color }}>{stress.index}</b>
        </div>

        <div className="fr-sd-sec">Why it's {stress.label} right now — what's driving it</div>
        <div className="fr-sd-contribs">
          {contribs.map((c) => (
            <button key={c.portid} className="fr-sd-c" onClick={() => { onPickEntity?.(c.portid); onClose(); }}>
              <span className="fr-sd-c-top">
                <span className="fr-sd-c-name">{c.name}</span>
                <span className="fr-sd-c-num">
                  {Math.round(c.now)}/day vs {Math.round(c.normal)} normal
                  <b style={{ color: c.pct_vs_normal < 0 ? '#c0392b' : '#b07b1e' }}>
                    {' '}({c.pct_vs_normal > 0 ? '+' : ''}{Math.round(c.pct_vs_normal)}%)
                  </b>
                </span>
              </span>
              <span className="fr-sd-c-bar"><i style={{ width: `${(c.contribution / maxC) * 100}%`, background: lv.color }} /></span>
            </button>
          ))}
          {!contribs.length && <div className="fr-sd-none">No chokepoint is meaningfully off its normal right now.</div>}
        </div>

        {(stress.fastest_deteriorating || stress.most_improved) && (
          <div className="fr-sd-movers">
            {stress.fastest_deteriorating && <span>↗ deteriorating fastest: <b>{stress.fastest_deteriorating.name}</b></span>}
            {stress.most_improved && <span>↘ most improved: <b>{stress.most_improved.name}</b></span>}
          </div>
        )}

        <div className="fr-sd-scale">
          {SCALE.map((s) => (
            <span key={s.label} className={s.label === stress.label ? 'on' : ''}>{s.label} <i>{s.range}</i></span>
          ))}
        </div>
        <div className="fr-sd-foot">Source: {stress.source} · as of {stress.as_of}. Click any driver to see it on the globe.</div>
      </div>
    </div>
  );
}
