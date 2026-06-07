import { useMemo, useState } from 'react';
import type { AppData, MonitorEntity } from '../types.ts';
import { computeNearby, ASSOCIATION_ONLY } from '../lib/nearby.ts';

interface NearbyPanelProps {
  entity: MonitorEntity | null;
  data: AppData;
  onClose: () => void;
}

const RADII = [500, 750, 1500] as const;

// The P6 cross-layer surface, made visible. Select a port/chokepoint and this lists the
// cited CONTEXT already on the globe that sits within a radius of it — ordered ONLY by
// distance. Deliberately NOT a leaderboard: no severity sort, no count-as-risk, no
// historical base-rate. A neutral roster of co-located receipts the reader weighs.
export default function NearbyPanel({ entity, data, onClose }: NearbyPanelProps) {
  const [radius, setRadius] = useState<number>(750);

  const items = useMemo(() => {
    if (!entity || entity.lat == null || entity.lon == null) return [];
    return computeNearby(entity.lat, entity.lon, radius, data);
  }, [entity, radius, data]);

  if (!entity || entity.lat == null || entity.lon == null) return null;

  return (
    <aside className="fr-nearby" aria-label={`Cited context near ${entity.name}`}>
      <div className="fr-nearby-head">
        <div>
          <span className="fr-nearby-eyebrow">cited context near</span>
          <h3 className="fr-nearby-title">{entity.name}</h3>
        </div>
        <button className="fr-nearby-x" onClick={onClose} aria-label="Close nearby panel">
          ×
        </button>
      </div>

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
        {items.length} cited item{items.length === 1 ? '' : 's'} within {radius} km, ordered by
        distance. {ASSOCIATION_ONLY}
      </p>

      {items.length === 0 ? (
        <p className="fr-nearby-empty">
          No cited context within {radius} km right now — widen the radius or toggle more layers.
        </p>
      ) : (
        <ul className="fr-nearby-list">
          {items.map((it, i) => {
            const row = (
              <>
                <span className="fr-nearby-km">{it.km} km</span>
                <span className="fr-nearby-body">
                  <span className="fr-nearby-label">{it.label}</span>
                  {it.place && <span className="fr-nearby-place">{it.place}</span>}
                  {it.detail && <span className="fr-nearby-detail">{it.detail}</span>}
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
    </aside>
  );
}
