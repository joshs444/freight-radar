import { useMemo, useRef } from 'react';
import type { History } from '../types.ts';

// The "play through history" timeline: the Global Ocean Freight Stress Index across
// PortWatch's full 2019→now record as a line, with the real shocks marked (COVID, Ever
// Given, Panama drought, Red Sea…), a moving playhead, and a keyboard-accessible
// scrubber. Honest: the line is the same breadth+depth composite as the live index, and
// the event markers are curated + source-cited (never generated).

interface HistoryTimelineProps {
  history: History;
  week: number;
  playing: boolean;
  onWeek: (w: number) => void;
  onPlayToggle: () => void;
  onClose: () => void;
}

const VW = 1000;
const VH = 150;
const PAD_X = 6;
const PAD_TOP = 14;
const PAD_BOT = 18;

function stressLabel(s: number): string {
  if (s >= 55) return 'severe';
  if (s >= 35) return 'high';
  if (s >= 15) return 'elevated';
  return 'calm';
}

export default function HistoryTimeline({
  history,
  week,
  playing,
  onWeek,
  onPlayToggle,
  onClose,
}: HistoryTimelineProps) {
  const { dates, stress, events } = history;
  const n = dates.length;
  const svgRef = useRef<SVGSVGElement>(null);

  const maxStress = useMemo(() => Math.max(50, ...stress), [stress]);
  const xAt = (i: number) => PAD_X + (i / Math.max(1, n - 1)) * (VW - 2 * PAD_X);
  const yAt = (s: number) => VH - PAD_BOT - (s / maxStress) * (VH - PAD_TOP - PAD_BOT);

  const { line, area } = useMemo(() => {
    const pts = stress
      .map((s, i) => `${i ? 'L' : 'M'}${xAt(i).toFixed(1)} ${yAt(s).toFixed(1)}`)
      .join(' ');
    return {
      line: pts,
      area: `${pts} L${xAt(n - 1).toFixed(1)} ${VH - PAD_BOT} L${xAt(0).toFixed(1)} ${VH - PAD_BOT} Z`,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [stress, maxStress, n]);

  const nearestIdx = (iso: string) => {
    const t = Date.parse(iso);
    let best = 0;
    let bd = Infinity;
    for (let i = 0; i < n; i++) {
      const d = Math.abs(Date.parse(dates[i]) - t);
      if (d < bd) {
        bd = d;
        best = i;
      }
    }
    return best;
  };
  const eventMarks = useMemo(
    () => events.map((e) => ({ e, i: nearestIdx(e.date) })),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [events, dates]
  );

  // year ticks for orientation
  const years = useMemo(() => {
    const out: { y: number; i: number }[] = [];
    let last = '';
    for (let i = 0; i < n; i++) {
      const yr = dates[i].slice(0, 4);
      if (yr !== last) {
        out.push({ y: Number(yr), i });
        last = yr;
      }
    }
    return out;
  }, [dates, n]);

  const setFromClientX = (clientX: number) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const frac = (clientX - rect.left) / rect.width;
    onWeek(Math.max(0, Math.min(n - 1, Math.round(frac * (n - 1)))));
  };

  const curDate = dates[week] ?? dates[n - 1];
  const curStress = stress[week] ?? 0;
  const px = xAt(week);

  return (
    <div className="fr-hist">
      <div className="fr-hist-top">
        <div className="fr-hist-title">
          <span className="fr-hist-kicker">History · play 2019 → today</span>
          <span className="fr-hist-readout">
            <b>{curDate}</b> · Ocean Freight Stress{' '}
            <b style={{ color: 'var(--amber)' }}>{curStress.toFixed(0)}</b>/100 (
            {stressLabel(curStress)})
          </span>
        </div>
        <button className="fr-hist-close" onClick={onClose} aria-label="Exit history mode">
          ← Live
        </button>
      </div>

      <svg
        ref={svgRef}
        className="fr-hist-svg"
        viewBox={`0 0 ${VW} ${VH}`}
        preserveAspectRatio="none"
        role="img"
        aria-label="Global ocean-freight stress index, 2019 to today"
        onMouseDown={(e) => setFromClientX(e.clientX)}
      >
        {years.map((yr) => (
          <g key={yr.y}>
            <line
              x1={xAt(yr.i)}
              y1={PAD_TOP}
              x2={xAt(yr.i)}
              y2={VH - PAD_BOT}
              className="fr-hist-grid"
            />
            <text x={xAt(yr.i) + 3} y={VH - 5} className="fr-hist-year">
              {yr.y}
            </text>
          </g>
        ))}
        <path d={area} className="fr-hist-area" />
        <path d={line} className="fr-hist-line" />
        {eventMarks.map(({ e, i }) => (
          <g key={e.id} className={`fr-hist-ev ${i <= week ? 'is-past' : ''}`}>
            <line
              x1={xAt(i)}
              y1={PAD_TOP}
              x2={xAt(i)}
              y2={VH - PAD_BOT}
              className="fr-hist-ev-line"
            />
            <circle cx={xAt(i)} cy={yAt(stress[i] ?? 0)} r={3.2} className="fr-hist-ev-dot" />
          </g>
        ))}
        <line x1={px} y1={PAD_TOP - 6} x2={px} y2={VH - PAD_BOT} className="fr-hist-playhead" />
        <circle cx={px} cy={yAt(curStress)} r={4.5} className="fr-hist-playhead-dot" />
      </svg>

      <div className="fr-hist-controls">
        <button
          className="fr-hist-play"
          onClick={onPlayToggle}
          aria-label={playing ? 'Pause' : 'Play through history'}
        >
          {playing ? '❚❚' : '▶'}
        </button>
        <input
          className="fr-hist-range"
          type="range"
          min={0}
          max={n - 1}
          value={week}
          onChange={(e) => onWeek(Number(e.target.value))}
          aria-label="Scrub the history timeline"
        />
        <span className="fr-hist-note">
          PortWatch daily transits · index = our composite · events curated + cited
        </span>
      </div>
    </div>
  );
}
