import { useEffect, useRef } from 'react';
import { severityCss } from '../lib/colors.js';

const FRAME_MS = 130; // playback speed (~7.7 days/sec)

function fmt(d) {
  // 'YYYY-MM-DD' -> 'DD Mon'
  const [, m, day] = d.split('-');
  const mon = [
    '',
    'Jan',
    'Feb',
    'Mar',
    'Apr',
    'May',
    'Jun',
    'Jul',
    'Aug',
    'Sep',
    'Oct',
    'Nov',
    'Dec',
  ][+m];
  return `${day} ${mon}`;
}

export default function TimeScrubber({
  timeseries,
  index,
  playing,
  onChange,
  onPlayToggle,
  onLive,
}) {
  const { dates, flags } = timeseries;
  const n = dates.length;
  const live = index === null;
  const cur = live ? n - 1 : index;
  const raf = useRef(null);

  // playback loop
  useEffect(() => {
    if (!playing) return;
    let last = 0;
    let i = live ? 0 : cur;
    const tick = (t) => {
      if (t - last >= FRAME_MS) {
        last = t;
        i += 1;
        if (i >= n) {
          onLive(); // reached the present -> snap back to live
          return;
        }
        onChange(i);
      }
      raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [playing]);

  // flag tick marks positioned along the timeline by their date index
  const ticks = flags.map((f) => ({ ...f, i: dates.indexOf(f.as_of) })).filter((f) => f.i >= 0);

  return (
    <div className="fr-scrubber">
      <button className="fr-play" onClick={onPlayToggle} aria-label={playing ? 'pause' : 'play'}>
        {playing ? '❚❚' : '▶'}
      </button>

      <div className="fr-track-wrap">
        <div className="fr-ticks">
          {ticks.map((f) => (
            <span
              key={f.flag_id}
              className="fr-tick"
              title={`${f.entity} · ${fmt(f.as_of)}`}
              style={{ left: `${(f.i / (n - 1)) * 100}%`, background: severityCss(f.severity) }}
            />
          ))}
        </div>
        <input
          className="fr-range"
          type="range"
          min={0}
          max={n - 1}
          value={cur}
          onChange={(e) => onChange(+e.target.value)}
        />
      </div>

      <div className="fr-date">{fmt(dates[cur])}</div>
      <button className={`fr-livebtn ${live ? 'on' : ''}`} onClick={onLive}>
        <span className="fr-livedot" /> LIVE
      </button>
    </div>
  );
}
