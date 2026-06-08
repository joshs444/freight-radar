// Source provenance now flows FROM the data, never a parallel client-side map.
//
// Until P0-B, a 17-entry regex here pattern-matched a flag's free-text `source` string to a home
// URL — a second URL table that could silently drift from the backend registry SSOT. That regex
// is gone: every datapoint that needs a link now carries its own `source_url`, stamped from the
// registry root (flags via detect/detectors.py, signals via signal_pool.py). The only thing left
// is cosmetic — trimming a verbose source string to its clean provider name for a trace label.

// Trim a verbose source string ("IMF PortWatch — daily granularity, refreshed weekly") to its
// clean provider name ("IMF PortWatch") for the trace label.
export function sourceName(source?: string | null): string {
  if (!source) return 'source';
  return source.split(/\s+[—·|(]/)[0].trim();
}
