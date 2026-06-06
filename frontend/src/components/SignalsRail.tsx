import type { NewsGeo, Quakes, Disruptions, Gatun } from '../types.ts';

// The Board's right rail. Two honest tiers, kept visually separate:
//   MEASURED signal  — Gatun: numbers WE compute over a cited ACP source (pctile, deltas,
//                      min-draft). Labelled "computed by us", not borrowed.
//   CONTEXT          — GDELT news + USGS quakes + GDACS hazards: someone else's raw cited
//                      values shown as-is, time-sorted, each a click-through to its source.
//                      Every item is "possibly-related, not a stated cause".

interface SignalsRailProps {
  newsGeo: NewsGeo | null;
  quakes: Quakes | null;
  disruptions: Disruptions | null;
  gatun: Gatun | null;
}

interface RailItem {
  kind: 'news' | 'quake' | 'hazard';
  time: string;
  title: string;
  sub: string;
  url?: string;
  tag: string;
}

const CAP = 20;

function buildItems(
  newsGeo: NewsGeo | null,
  quakes: Quakes | null,
  disruptions: Disruptions | null
): RailItem[] {
  const items: RailItem[] = [];
  (newsGeo?.items ?? []).slice(0, 60).forEach((n) =>
    items.push({
      kind: 'news',
      time: n.seen,
      title: `${n.category_label} · ${n.place}`,
      sub: n.domain,
      url: n.url,
      tag: n.category,
    })
  );
  (quakes?.items ?? []).slice(0, 40).forEach((q) =>
    items.push({
      kind: 'quake',
      time: q.time,
      title: `M${q.mag.toFixed(1)} · ${q.place}`,
      sub: `${q.depth_km != null ? `${q.depth_km} km deep` : 'USGS'}${q.tsunami ? ' · 🌊' : ''}`,
      url: q.url,
      tag: 'seismic',
    })
  );
  (disruptions?.events ?? []).slice(0, 30).forEach((e) =>
    items.push({
      kind: 'hazard',
      time: e.to || e.from,
      title: `${e.type_label} · ${e.name}`.slice(0, 60),
      sub: `${e.alertlevel}${e.country ? ' · ' + e.country : ''}`,
      url: disruptions?.source_url,
      tag: e.alertlevel?.toLowerCase() || 'hazard',
    })
  );
  // newest first (the timestamps are ISO-ish strings, so a string sort is chronological)
  items.sort((a, b) => (b.time || '').localeCompare(a.time || ''));
  return items.slice(0, CAP);
}

export default function SignalsRail({ newsGeo, quakes, disruptions, gatun }: SignalsRailProps) {
  const items = buildItems(newsGeo, quakes, disruptions);

  return (
    <aside className="fr-signals-rail" aria-label="Signals">
      {gatun?.available && (
        <section className="fr-rail-sec">
          <div className="fr-rail-head">
            <span>Measured signal</span>
            <span className="fr-rail-tag-meas">computed by us</span>
          </div>
          <a
            className="fr-rail-gatun"
            href={gatun.source_url}
            target="_blank"
            rel="noopener noreferrer"
            title="Panama Canal — Gatún lake level (we compute percentile + draft from the ACP record)"
          >
            <div className="fr-rail-gatun-top">
              <b>Gatún {gatun.current_level_ft}ft</b>
              <span className="fr-dim">p{gatun.pctile_alltime} all-time</span>
            </div>
            <div className="fr-rail-gatun-sub">
              neopanamax draft {gatun.min_projected_neopanamax_draft_ft}ft
              {gatun.surcharge_pct_now ? ` · surcharge +${gatun.surcharge_pct_now}%` : ''}
              {gatun.draft_restricted ? ' · ⚠ restricted' : ''}
            </div>
          </a>
        </section>
      )}

      <section className="fr-rail-sec">
        <div className="fr-rail-head">
          <span>Context · {items.length}</span>
          <span className="fr-rail-tag-ctx">possibly-related, not a cause</span>
        </div>
        <ul className="fr-rail-list">
          {items.map((it, i) => {
            const inner = (
              <>
                <span className={`fr-rail-dot k-${it.kind}`} aria-hidden />
                <span className="fr-rail-body">
                  <span className="fr-rail-title">{it.title}</span>
                  <span className="fr-rail-meta">
                    {it.time} · {it.sub}
                  </span>
                </span>
              </>
            );
            return (
              <li key={`${it.kind}-${i}`} className="fr-rail-item">
                {it.url ? (
                  <a
                    href={it.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    title="Open the cited source"
                  >
                    {inner}
                  </a>
                ) : (
                  <span>{inner}</span>
                )}
              </li>
            );
          })}
          {!items.length && <li className="fr-rail-empty">No cited signals loaded.</li>}
        </ul>
        <p className="fr-rail-foot">
          Sources: GDELT · USGS · GDACS — shown as-is, dated, never a stated cause or a forecast.
        </p>
      </section>
    </aside>
  );
}
