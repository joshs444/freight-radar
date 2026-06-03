// Warm/cool identity: chokepoints = amber (watched), ports = cyan (ambient).
export const AMBER = [255, 158, 44];
export const CYAN = [54, 224, 232];
export const LANE = [122, 142, 255];

// Severity ramp 0 -> 100 : teal-green -> amber -> orange -> red.
const RAMP = [
  [0, [64, 209, 160]],
  [35, [255, 206, 84]],
  [65, [255, 142, 60]],
  [100, [255, 73, 79]],
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
