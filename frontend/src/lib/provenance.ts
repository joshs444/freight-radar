// Resolve a layer/flag's free-text source string to its canonical home URL, so every clickable
// datapoint can trace back to where the number actually came from. Mirrors the source URLs in the
// backend layer registry (backend/freight_radar/registry/) — the same SSOT the Source Ledger uses.

const SOURCE_URLS: [RegExp, string][] = [
  [/portwatch/i, 'https://portwatch.imf.org'],
  [/fred|st\.?\s*louis/i, 'https://fred.stlouisfed.org'],
  [/gdacs/i, 'https://www.gdacs.org'],
  [/usgs water|waterservices/i, 'https://waterservices.usgs.gov'],
  [/usgs/i, 'https://earthquake.usgs.gov'],
  [/eonet|nasa.*eonet/i, 'https://eonet.gsfc.nasa.gov'],
  [/gibs|viirs/i, 'https://gibs.earthdata.nasa.gov'],
  [/nhc/i, 'https://www.nhc.noaa.gov'],
  [/gfs|nomads/i, 'https://nomads.ncep.noaa.gov'],
  [/swpc/i, 'https://www.swpc.noaa.gov'],
  [/co-?ops|tidesandcurrents/i, 'https://tidesandcurrents.noaa.gov'],
  [/open-?meteo/i, 'https://open-meteo.com'],
  [/gdelt/i, 'https://www.gdeltproject.org'],
  [/google news/i, 'https://news.google.com'],
  [/aisstream/i, 'https://aisstream.io'],
  [/panama canal|\bacp\b|pancanal/i, 'https://pancanal.com'],
  [/stooq/i, 'https://stooq.com'],
];

export function sourceUrl(source?: string | null): string | null {
  if (!source) return null;
  for (const [re, url] of SOURCE_URLS) if (re.test(source)) return url;
  return null;
}

// Trim a verbose source string ("IMF PortWatch — daily granularity, refreshed weekly") to its
// clean provider name ("IMF PortWatch") for the trace label.
export function sourceName(source?: string | null): string {
  if (!source) return 'source';
  return source.split(/\s+[—·|(]/)[0].trim();
}
