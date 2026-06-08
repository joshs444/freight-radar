import { useMemo, useState } from 'react';
import type { AppData, MonitorEntity } from '../types.ts';
import { computeNearby, ASSOCIATION_ONLY } from '../lib/nearby.ts';
import { useCatalog } from '../lib/catalog.ts';

interface NearbyPanelProps {
  entity: MonitorEntity | null;
  data: AppData;
  onClose: () => void;
}

const RADII = [500, 750, 1500] as const;
const FAMILY_LABEL: Record<string, string> = {
  freight_rate: 'freight rate',
  slack: 'inventories',
  macro: 'macro',
  commodities: 'commodity',
  metals: 'metals',
  labor: 'labor',
};

// "What's near here", as two structurally-separated zones — the separation IS the product (§3):
//   ZONE 1 "Here, specifically" — only things with a real location at/near this point: this flag's
//     OWN cited news (news.json keyed by flag_id), its live_storm / official_event, and the
//     co-located cited context within a radius (computeNearby), ordered ONLY by distance.
//   ZONE 2 "System context — national / global, not this place" — the fenced cross-domain signals.
//     Place-INVARIANT: its content + order are a pure function of signals_fdr.json, byte-identical
//     for every place; it is NEVER distance-tagged, NEVER counted into Zone 1, NEVER attributed here.
// Honesty fences: no single "N converging" total; families stay separate + unsummed; one real event
// is de-duped across feeds (the storm chip flags its co-located twins); co-location is association,
// never cause, at every layer.
export default function NearbyPanel({ entity, data, onClose }: NearbyPanelProps) {
  const [radius, setRadius] = useState<number>(750);
  const catalog = useCatalog();

  const items = useMemo(() => {
    if (!entity || entity.lat == null || entity.lon == null) return [];
    return computeNearby(entity.lat, entity.lon, radius, data, catalog);
  }, [entity, radius, data, catalog]);

  const flag = entity?.flag ?? null;
  // Zone 1, place-attributable to THIS flag: its own cited news + storm + official event
  const articles = (flag && data.news?.items?.[flag.flag_id]?.items) || [];
  const storm = flag?.live_storm ?? null;
  const official = flag?.official_event ?? null;
  const hasOwn = articles.length > 0 || !!storm || !!official;

  // fence #3 — one real event is not N feeds: tag co-located rows that are the SAME storm
  const stormKey = storm?.name?.toLowerCase() ?? null;
  const isSameStorm = (place: string | null, detail: string | null) =>
    !!stormKey &&
    ((place?.toLowerCase().includes(stormKey) ?? false) ||
      (detail?.toLowerCase().includes(stormKey) ?? false));

  // Zone 2 — place-INVARIANT: computed purely from the global signals file, no entity reference
  const national = useMemo(
    () =>
      (data.signals?.items ?? [])
        .filter((s) => s.fdr_significant && s.fenced === 'national')
        .sort((a, b) => Math.abs(b.our_zscore) - Math.abs(a.our_zscore)),
    [data.signals]
  );

  if (!entity || entity.lat == null || entity.lon == null) return null;

  return (
    <aside className="fr-nearby" aria-label={`Cited context near ${entity.name}`}>
      <div className="fr-nearby-head">
        <div>
          <span className="fr-nearby-eyebrow">what's near</span>
          <h3 className="fr-nearby-title">{entity.name}</h3>
        </div>
        <button className="fr-nearby-x" onClick={onClose} aria-label="Close nearby panel">
          ×
        </button>
      </div>

      {/* ───────── ZONE 1: here, specifically ───────── */}
      <div className="fr-nearby-zone">
        <span className="fr-nearby-zonelabel">Here, specifically</span>

        {hasOwn && (
          <ul className="fr-nearby-list">
            {storm && (
              <li className="fr-nearby-row sw-storm">
                {storm.url ? (
                  <a href={storm.url} target="_blank" rel="noreferrer" className="fr-nearby-link">
                    <StormRow storm={storm} />
                  </a>
                ) : (
                  <span className="fr-nearby-link">
                    <StormRow storm={storm} />
                  </span>
                )}
              </li>
            )}
            {official && (
              <li className="fr-nearby-row sw-disruptions">
                <span className="fr-nearby-link">
                  <span className="fr-nearby-km">official</span>
                  <span className="fr-nearby-body">
                    <span className="fr-nearby-label">{official.type_label}</span>
                    <span className="fr-nearby-place">{official.name}</span>
                    <span className="fr-nearby-detail">{official.alertlevel} alert</span>
                  </span>
                  <span className="fr-nearby-src">{official.source}</span>
                </span>
              </li>
            )}
            {articles.map((a, i) => (
              <li key={`art-${i}`} className="fr-nearby-row sw-news_geo">
                <a href={a.url} target="_blank" rel="noreferrer" className="fr-nearby-link">
                  <span className="fr-nearby-km">news</span>
                  <span className="fr-nearby-body">
                    <span className="fr-nearby-label">{a.title}</span>
                    <span className="fr-nearby-detail">{a.published}</span>
                  </span>
                  <span className="fr-nearby-src">{a.source}</span>
                </a>
              </li>
            ))}
          </ul>
        )}

        <div className="fr-nearby-radii" role="group" aria-label="Search radius">
          {RADII.map((r) => (
            <button
              key={r}
              type="button"
              className={`fr-nearby-radius ${radius === r ? 'on' : ''}`}
              aria-pressed={radius === r}
              onClick={() => setRadius(r)}
            >
              {r >= 1000 ? `${r / 1000}k` : r} km
            </button>
          ))}
        </div>

        <p className="fr-nearby-note">
          {items.length} co-located cited item{items.length === 1 ? '' : 's'} within {radius} km,
          ordered by distance. {ASSOCIATION_ONLY}
        </p>

        {items.length === 0 ? (
          <p className="fr-nearby-empty">
            No co-located cited context within {radius} km right now — widen the radius or toggle
            more layers.
          </p>
        ) : (
          <ul className="fr-nearby-list">
            {items.map((it, i) => {
              const twin = isSameStorm(it.place, it.detail);
              const row = (
                <>
                  <span className="fr-nearby-km">{it.km} km</span>
                  <span className="fr-nearby-body">
                    <span className="fr-nearby-label">{it.label}</span>
                    {it.place && <span className="fr-nearby-place">{it.place}</span>}
                    {it.detail && <span className="fr-nearby-detail">{it.detail}</span>}
                    {twin && <span className="fr-nearby-same">same storm as above</span>}
                  </span>
                  {it.source && <span className="fr-nearby-src">{it.source}</span>}
                </>
              );
              return (
                <li key={`${it.layer}-${i}`} className={`fr-nearby-row sw-${it.layer}`}>
                  {it.url ? (
                    <a href={it.url} target="_blank" rel="noreferrer" className="fr-nearby-link">
                      {row}
                    </a>
                  ) : (
                    <span className="fr-nearby-link">{row}</span>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>

      {/* ───────── ZONE 2: system context, national/global — fenced ───────── */}
      {national.length > 0 && (
        <div className="fr-nearby-zone fenced">
          <span className="fr-nearby-zonelabel fenced">
            System context — national / global, not this place
          </span>
          <ul className="fr-nearby-natlist">
            {national.map((s) => {
              const up = s.our_zscore > 0;
              return (
                <li key={s.id} className="fr-nearby-nat">
                  <span className={`fr-nearby-natz ${up ? 'up' : 'down'}`}>
                    {up ? '▲' : '▼'} {up ? '+' : ''}
                    {s.our_zscore.toFixed(1)}σ
                  </span>
                  <span className="fr-nearby-natname">{s.name}</span>
                  {s.source_url ? (
                    <a
                      href={s.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="fr-nearby-natfam"
                    >
                      {FAMILY_LABEL[s.family] || s.family} ↗
                    </a>
                  ) : (
                    <span className="fr-nearby-natfam">{FAMILY_LABEL[s.family] || s.family}</span>
                  )}
                </li>
              );
            })}
          </ul>
          <p className="fr-nearby-fencenote">
            Measured national/global anomalies — a z-score we compute over cited public indices,
            FDR-controlled. Shown identically for every place; never attributed to this one, never
            distance-tagged. Association only, never a cause.
          </p>
        </div>
      )}
    </aside>
  );
}

// a live-storm row (the flag's own attached cyclone) in the Zone-1 roster
function StormRow({ storm }: { storm: NonNullable<MonitorEntity['flag']>['live_storm'] }) {
  if (!storm) return null;
  return (
    <>
      <span className="fr-nearby-km">
        {storm.km != null ? `${Math.round(storm.km)} km` : 'storm'}
      </span>
      <span className="fr-nearby-body">
        <span className="fr-nearby-label">{storm.name}</span>
        <span className="fr-nearby-detail">
          {storm.category}
          {storm.basin ? ` · ${storm.basin}` : ''}
        </span>
      </span>
      <span className="fr-nearby-src">{storm.agency || storm.source}</span>
    </>
  );
}
