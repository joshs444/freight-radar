// Compact USD: 149000000 -> "$149M", 1224658 -> "$1.2M", 28000000 -> "$28M".
export function money(v: number | null | undefined): string {
  if (v == null) return '—';
  const a = Math.abs(v);
  if (a >= 1e9) return `$${(v / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `$${(v / 1e6).toFixed(a < 1e7 ? 1 : 0)}M`;
  if (a >= 1e3) return `$${Math.round(v / 1e3)}K`;
  return `$${Math.round(v)}`;
}

// Compact count: 1947 -> "1,947", 4797 -> "4,797", 32561126 -> "32.6M".
export function compact(v: number | null | undefined): string {
  if (v == null) return '—';
  const a = Math.abs(v);
  if (a >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (a >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  return Math.round(v).toLocaleString('en-US');
}
