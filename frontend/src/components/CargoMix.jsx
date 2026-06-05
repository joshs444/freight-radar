// Per-entity vessel mix — the share of each leaf cargo type in an entity's daily
// flow (chokepoint transits or port calls). The 5 types sum to the headline total
// (PortWatch invariant), so the bar is always 100%. Sourced straight from the
// snapshot's `cargo_mix` (no estimate) — answers "WHAT moves through here, not just
// how much". A tanker-heavy strait vs a container-heavy port reads at a glance.

const CARGO_ORDER = ['container', 'tanker', 'dry_bulk', 'general_cargo', 'roro'];
const CARGO_LABEL = {
  container: 'Container',
  tanker: 'Tanker',
  dry_bulk: 'Dry bulk',
  general_cargo: 'Gen. cargo',
  roro: 'RoRo',
};
const CARGO_COLOR = {
  container: '#3a6ea5',
  tanker: '#c2611f',
  dry_bulk: '#8a6d3b',
  general_cargo: '#5b8a72',
  roro: '#7a6a9a',
};

import { compact } from '../lib/format.js';

export default function CargoMix({ mix, unit = 'transits', avgSize, tonnage }) {
  if (!mix) return null;
  const total = CARGO_ORDER.reduce((s, k) => s + (mix[k] || 0), 0);
  if (!total) return null;
  const parts = CARGO_ORDER.map((k) => ({ k, n: mix[k] || 0, pct: ((mix[k] || 0) / total) * 100 }))
    .filter((p) => p.n > 0)
    .sort((a, b) => b.n - a.n);
  const dominant = parts[0];
  return (
    <div className="fr-cargo">
      <div className="fr-cargo-head">
        Vessel mix{' '}
        <span>
          · by {unit} · {total.toLocaleString()} latest day
        </span>
      </div>
      <div className="fr-cargo-bar">
        {parts.map((p) => (
          <span
            key={p.k}
            className="fr-cargo-seg"
            style={{ width: `${p.pct}%`, background: CARGO_COLOR[p.k] }}
            title={`${CARGO_LABEL[p.k]} — ${p.n} (${Math.round(p.pct)}%)`}
          />
        ))}
      </div>
      <div className="fr-cargo-legend">
        {parts.map((p) => (
          <span key={p.k} className="fr-cargo-leg">
            <span className="fr-cargo-dot" style={{ background: CARGO_COLOR[p.k] }} />
            {CARGO_LABEL[p.k]} <b>{Math.round(p.pct)}%</b>
          </span>
        ))}
      </div>
      {avgSize ? (
        <div className="fr-cargo-tonnage">
          <span>
            <b>~{compact(avgSize)}</b> DWT avg vessel
          </span>
          {tonnage ? (
            <span>
              <b>{compact(tonnage)}</b> DWT transiting
            </span>
          ) : null}
          <span className="fr-cargo-note">size = tonnage ÷ vessels, not utilization</span>
        </div>
      ) : null}
      <div className="fr-cargo-foot">
        {Math.round(dominant.pct)}% {CARGO_LABEL[dominant.k].toLowerCase()}-dominant · IMF PortWatch
      </div>
    </div>
  );
}
