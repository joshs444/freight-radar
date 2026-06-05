// Light-theme marks: deep amber chokepoints, slate port-dust, soft slate lanes.
export const AMBER = [230, 122, 14];
export const PORT = [71, 85, 105];
export const LANE = [128, 138, 158];
export const CYAN = [13, 148, 136]; // teal accent (used sparingly)

// Severity ramp 0 -> 100 : slate -> amber -> red, tuned to read on a light bg.
// No green (green = "all clear", wrong for an alert). Muted, not neon.
const RAMP: [number, number[]][] = [
  [0, [96, 116, 146]],
  [40, [223, 150, 52]],
  [70, [223, 110, 52]],
  [100, [214, 66, 66]],
];

export function severityColor(
  s: number | null | undefined,
  alpha = 255
): [number, number, number, number] {
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

export const severityCss = (s: number | null | undefined): string => {
  const [r, g, b] = severityColor(s);
  return `rgb(${r}, ${g}, ${b})`;
};

// Stress-index level → color/tint, matching the backend's calm/elevated/high/severe.
export const STRESS_LEVELS = {
  calm: { color: '#3f7a5a', tint: '#eef6f1', edge: '#cfe6d9' },
  elevated: { color: '#b07b1e', tint: '#fbf4e6', edge: '#f0e2c4' },
  high: { color: '#c2611f', tint: '#fbeee2', edge: '#f1d8bf' },
  severe: { color: '#c0392b', tint: '#fbecea', edge: '#f1cdc8' },
};
export const stressLevel = (label: string | null | undefined) =>
  STRESS_LEVELS[label as keyof typeof STRESS_LEVELS] || STRESS_LEVELS.calm;
