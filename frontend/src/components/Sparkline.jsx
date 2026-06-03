// Clean-line SVG sparklines — tiny inline trend + a detailed history chart.

export function Sparkline({ values, width = 62, height = 20, color = '#9aa6bd', strokeWidth = 1.3 }) {
  if (!values || values.length < 2) return <span className="fr-spark-empty" />;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const n = values.length;
  const x = (i) => (i / (n - 1)) * width;
  const y = (v) => height - ((v - min) / range) * (height - 2) - 1;
  const d = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  return (
    <svg className="fr-spark" width={width} height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <path d={d} fill="none" stroke={color} strokeWidth={strokeWidth} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function SparkHistory({ s, dates, asOf, baseline, color = '#e07b12' }) {
  if (!s?.values || s.values.length < 2) return null;
  const values = s.values;
  const W = 340, H = 60, pad = 2;
  const min = Math.min(...values, baseline ?? Infinity);
  const max = Math.max(...values, baseline ?? -Infinity);
  const range = max - min || 1;
  const n = values.length;
  const x = (i) => pad + (i / (n - 1)) * (W - 2 * pad);
  const y = (v) => H - pad - ((v - min) / range) * (H - 2 * pad);
  const line = values.map((v, i) => `${i ? 'L' : 'M'}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(' ');
  const area = `${line} L ${x(n - 1).toFixed(1)} ${H - pad} L ${x(0).toFixed(1)} ${H - pad} Z`;
  const markerIdx = asOf && dates ? dates.indexOf(asOf) : -1;
  const cur = values[values.length - 1];

  return (
    <div className="fr-history">
      <svg className="fr-histsvg" viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" width="100%" height={H}>
        {baseline != null && (
          <line x1={pad} x2={W - pad} y1={y(baseline)} y2={y(baseline)}
            stroke="#c4ccd6" strokeWidth="1" strokeDasharray="3 3" />
        )}
        <path d={area} fill={color} opacity="0.1" />
        <path d={line} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" />
        {markerIdx >= 0 && (
          <line x1={x(markerIdx)} x2={x(markerIdx)} y1={pad} y2={H - pad}
            stroke="#d64242" strokeWidth="1" strokeDasharray="2 2" />
        )}
        <circle cx={x(n - 1)} cy={y(cur)} r="2.4" fill={color} />
      </svg>
      <div className="fr-histmeta">
        <span>now <b>{Math.round(cur)}</b></span>
        {baseline != null && <span>norm ~{Math.round(baseline)}</span>}
        <span>range {Math.round(min)}–{Math.round(max)}</span>
        <span className="fr-dim">{s.metric} · 120d</span>
      </div>
    </div>
  );
}
