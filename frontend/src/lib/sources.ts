// Small shared source helpers, so a URL builder lives in ONE place instead of being copy-pasted
// across Globe.tsx and nearby.ts (where the GDACS report link was duplicated verbatim).

// The canonical GDACS event-report page for a hazard. eventtype is GDACS's short code (EQ/TC/FL/…).
export function gdacsReportUrl(eventtype: string, eventid: number | string): string {
  return `https://www.gdacs.org/report.aspx?eventtype=${eventtype}&eventid=${eventid}`;
}

// A clicked CONTEXT dot, normalized for the trace card (P1-C). It carries just enough to render the
// cited reading as-published, then resolve the layer's tier + source + honesty-note from the
// catalog (via layerId) — so a quake/news/hazard/marine dot traces UP (what it is, cited, with its
// honesty caveat) BEFORE it traces OUT (the deep link to the specific event). url is null for
// marine, which has no per-item link — the card then shows only the file-level Open-Meteo source.
export interface ContextPick {
  layerId: string; // a catalog layer id: quakes | news_geo | eonet | marine | tides | streamflow | disruptions
  title: string; // the place / event name / headline
  value?: string; // the published reading, as the source states it (e.g. "M5.2", "wave 3.4 m")
  asOf?: string; // observed / seen date
  url?: string | null; // deep link to the specific event/article (null = no per-item link)
}
