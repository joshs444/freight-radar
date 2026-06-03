// Recent-direction read off an entity's series — "which way is it moving now?"
const avg = (a) => (a.length ? a.reduce((s, v) => s + v, 0) / a.length : 0);

export function computeTrend(values, win = 10) {
  if (!values || values.length < win * 2) return null;
  const recent = avg(values.slice(-win));
  const prior = avg(values.slice(-win * 2, -win));
  const base = Math.abs(prior) > 1 ? Math.abs(prior) : Math.max(1, avg(values));
  const pct = Math.round(((recent - prior) / base) * 100);
  let dir = 'flat';
  if (pct > 8) dir = 'up';
  else if (pct < -8) dir = 'down';
  return { dir, pct, win };
}

// Interpret the raw direction against the disruption: is it easing or worsening?
export function trendLabel(t, kind) {
  if (!t) return null;
  const isDrop = kind && (kind.includes('collapse') || kind.includes('drop'));
  const isSpike = kind && (kind.includes('spike') || kind.includes('surge'));
  if (t.dir === 'flat') return { arrow: '→', label: kind ? 'holding' : 'stable', cls: 'tr-flat', pct: t.pct };
  if (isDrop)
    return t.dir === 'up'
      ? { arrow: '↗', label: 'recovering', cls: 'tr-good', pct: t.pct }
      : { arrow: '↘', label: 'deepening', cls: 'tr-bad', pct: t.pct };
  if (isSpike)
    return t.dir === 'down'
      ? { arrow: '↘', label: 'easing', cls: 'tr-good', pct: t.pct }
      : { arrow: '↗', label: 'intensifying', cls: 'tr-bad', pct: t.pct };
  // normal entity — neutral direction only
  return t.dir === 'up'
    ? { arrow: '↑', label: 'rising', cls: 'tr-flat', pct: t.pct }
    : { arrow: '↓', label: 'falling', cls: 'tr-flat', pct: t.pct };
}
