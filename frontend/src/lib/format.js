// Compact USD: 149000000 -> "$149M", 1224658 -> "$1.2M", 28000000 -> "$28M".
export function money(v) {
  if (v == null) return '—';
  const a = Math.abs(v);
  if (a >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `$${(v / 1e6).toFixed(a < 1e7 ? 1 : 0)}M`;
  if (a >= 1e3) return `$${Math.round(v / 1e3)}K`;
  return `$${Math.round(v)}`;
}
