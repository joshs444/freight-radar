import type { LayerId, LayerVisibility, Ships } from '../types.ts';

// The globe layer control + key, replacing the old caption-only legend (where the wind
// toggle hid among static text and nothing else could be turned off). Every overlay is a
// labelled on/off with a live count. The vessels row carries the HONEST scope — a
// point-in-time AIS sample near the 28 chokepoints, not all ships, not the ~2,000 ports.

const ROWS: { id: LayerId; label: string; sw: string }[] = [
  { id: 'flags', label: 'flagged', sw: 'pulse' },
  { id: 'chokepoints', label: 'chokepoints', sw: 'amber' },
  { id: 'ports', label: 'ports', sw: 'port' },
  { id: 'ships', label: 'vessels', sw: 'ship' },
  { id: 'storms', label: 'storms', sw: 'storm' },
  { id: 'lanes', label: 'lanes', sw: 'lane' },
  { id: 'wind', label: 'wind', sw: 'wind' },
  { id: 'satellite', label: 'satellite', sw: 'sat' },
];

// VIIRS true-color is published ~a day behind; matches Globe's GIBS_DATE (2 days back).
const SAT_DATE = (() => {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 2);
  return d.toISOString().slice(0, 10);
})();

interface LayerPanelProps {
  layers: LayerVisibility;
  onToggle: (id: LayerId) => void;
  counts: Partial<Record<LayerId, number>>;
  ships: Ships | null;
  shipCoverage?: number;
  hasWind: boolean;
}

export default function LayerPanel({
  layers,
  onToggle,
  counts,
  ships,
  shipCoverage,
  hasWind,
}: LayerPanelProps) {
  const portsN = counts.ports ?? 0;
  const rows = ROWS.filter((r) => {
    if (r.id === 'wind') return hasWind;
    if (r.id === 'storms') return (counts.storms ?? 0) > 0;
    if (r.id === 'ships') return (ships?.count ?? 0) > 0;
    return true;
  });

  return (
    <div className="fr-layers" aria-label="Map layers">
      <div className="fr-layers-head">Layers</div>
      {rows.map((r) => {
        const on = layers[r.id];
        const n = counts[r.id];
        return (
          <button
            key={r.id}
            type="button"
            className={`fr-layer ${on ? 'on' : 'off'}`}
            onClick={() => onToggle(r.id)}
            aria-pressed={on}
            title={
              r.id === 'ships' && ships
                ? ships.note
                : r.id === 'satellite'
                  ? `Real NASA VIIRS true-color satellite · ${SAT_DATE} (near-real-time)`
                  : `${on ? 'Hide' : 'Show'} the ${r.label} layer`
            }
          >
            <i className={`sw ${r.sw}`} />
            <span className="fr-layer-label">{r.label}</span>
            {n != null && r.id !== 'wind' && (
              <span className="fr-layer-n">{n.toLocaleString()}</span>
            )}
            <span className="fr-layer-switch" aria-hidden="true" />
          </button>
        );
      })}
      {(ships?.count ?? 0) > 0 && (
        <p className="fr-layers-note">
          Vessels = a point-in-time AIS sample
          {shipCoverage
            ? ` near ${shipCoverage} of the 28 chokepoints right now`
            : ' near the 28 chokepoints'}{' '}
          — not all ships, not the {portsN.toLocaleString()} ports.
        </p>
      )}
    </div>
  );
}
