// Warm/cool identity: chokepoints = amber (watched), ports = cyan (ambient).
export const AMBER = [255, 158, 44];
export const CYAN = [54, 224, 232];
export const LANE = [122, 142, 255];

// Severity ramp 0 -> 100 : cool slate -> warm amber -> red. No green
// (green reads "all clear", wrong for an alert). Muted, not neon.
const RAMP = [
  [0, [125, 142, 170]],
  [40, [224, 168, 96]],
  [70, [233, 130, 74]],
  [100, [231, 92, 86]],
];

export function severityColor(s, alpha = 255) {
  const v = Math.max(0, Math.min(100, s ?? 0));
  let lo = RAMP[0];
  let hi = RAMP[RAMP.length - 1];
  for (let i = 0; i < RAMP.length - 1; i++) {
    if (v >= RAMP[i][0] && v <= RAMP[i + 1][0]) {
      lo = RAMP[i];
      hi = RAMP[i + 1];
      break;
    }
  }
  const t = hi[0] === lo[0] ? 0 : (v - lo[0]) / (hi[0] - lo[0]);
  const c = lo[1].map((ch, i) => Math.round(ch + (hi[1][i] - ch) * t));
  return [c[0], c[1], c[2], alpha];
}

export const severityCss = (s) => {
  const [r, g, b] = severityColor(s);
  return `rgb(${r}, ${g}, ${b})`;
};
