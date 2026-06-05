import type { Flag } from '../types.ts';

export type TrendDir = 'up' | 'down' | 'flat';

export interface Trend {
  dir: TrendDir;
  pct: number;
  win: number;
}

export interface TrendLabel {
  arrow: string;
  label: string;
  cls: string;
  pct: number;
}

// Recent-direction read off an entity's series — "which way is it moving now?"
const avg = (a: number[]): number => (a.length ? a.reduce((s, v) => s + v, 0) / a.length : 0);

export function computeTrend(values: number[] | null | undefined, win = 10): Trend | null {
  if (!values || values.length < win * 2) return null;
  const recent = avg(values.slice(-win));
  const prior = avg(values.slice(-win * 2, -win));
  const base = Math.abs(prior) > 1 ? Math.abs(prior) : Math.max(1, avg(values));
  const pct = Math.round(((recent - prior) / base) * 100);
  let dir: TrendDir = 'flat';
  if (pct > 8) dir = 'up';
  else if (pct < -8) dir = 'down';
  return { dir, pct, win };
}

// Interpret the raw direction against the disruption: is it easing or worsening?
export function trendLabel(t: Trend | null, kind?: Flag['kind']): TrendLabel | null {
  if (!t) return null;
  const isDrop = kind && (kind.includes('collapse') || kind.includes('drop'));
  const isSpike = kind && (kind.includes('spike') || kind.includes('surge'));
  if (t.dir === 'flat')
    return { arrow: '→', label: kind ? 'holding' : 'stable', cls: 'tr-flat', pct: t.pct };
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
