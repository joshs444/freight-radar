import { useState } from 'react';
import type { SignalsFdr, SignalItem } from '../types.ts';
import { Sparkline } from './Sparkline.tsx';
import { sourceName } from '../lib/provenance.ts';

// The cross-domain measured signals, promoted from the SQL console to a first-class feed
// panel: the non-maritime anomalies we already compute — freight-mode rates (truckload/rail/
// air), inventories-to-sales, commodities, metals, macro — sitting alongside the port flags so
// the product reads as multi-domain, not straits-only. National + monthly, so no globe marker;
// a z-score WE compute over cited public indices, FDR-controlled, association only.

const FAMILY_LABEL: Record<string, string> = {
  freight_rate: 'freight rate',
  slack: 'inventories',
  macro: 'macro',
  commodities: 'commodity',
  metals: 'metals',
  labor: 'labor',
};

interface SignalBoardProps {
  signals: SignalsFdr | null | undefined;
}

// The per-row trace: this is the richest *measured* tier on the site, and (pre-P0-A) the only one
// with no click-to-source. Fence #5 from the plan — the z-score is OURS, the index is CITED; the
// RAW line and the COMPUTED-BY-US line must never collapse into "from FRED" on the anomaly.
// (P1-A will refactor this onto the shared <Trace> primitive; the honest shape is fixed here.)
function SignalTrace({ s }: { s: SignalItem }) {
  const zs = (s.z_series ?? []).map((p) => p.z);
  const up = s.our_zscore > 0;
  return (
    <div className="fr-prov fr-sig-trace">
      <span className="fr-prov-tier fr-tier-measured">measured · z computed in Python</span>
      <div className="fr-prov-trace">
        <span className="fr-prov-step">
          RAW: <b>{s.name}</b>
          {s.unit ? ` (${s.unit})` : ''} — cited from{' '}
          {s.source_url ? (
            <a
              href={s.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="fr-prov-src"
            >
              {sourceName(s.source)} ↗
            </a>
          ) : (
            <b>{sourceName(s.source)}</b>
          )}
        </span>
        {s.method && <span className="fr-prov-step">COMPUTED BY US: {s.method}</span>}
        <span className="fr-prov-step">
          published: z = {up ? '+' : ''}
          {s.our_zscore.toFixed(2)}σ
        </span>
        <span className="fr-prov-step">as of {s.as_of}</span>
      </div>
      {zs.length >= 2 && (
        <div className="fr-sig-spark">
          <Sparkline values={zs} width={132} height={26} color={up ? '#b0521e' : '#2f6f8f'} />
          <span className="fr-sig-spark-cap">36-mo computed z-track</span>
        </div>
      )}
    </div>
  );
}

export default function SignalBoard({ signals }: SignalBoardProps) {
  const [open, setOpen] = useState(true);
  const [openId, setOpenId] = useState<string | null>(null);
  const sig = (signals?.items ?? [])
    .filter((s) => s.fdr_significant)
    .sort((a, b) => Math.abs(b.our_zscore) - Math.abs(a.our_zscore));
  if (!sig.length) return null;

  return (
    <section className="fr-sigboard">
      <button
        type="button"
        className="fr-sigboard-top"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <div className="fr-sigboard-titles">
          <span className="fr-sigboard-kicker">Cross-domain signals</span>
          <span className="fr-sigboard-sub">
            {sig.length} measured anomalies beyond the straits — trucking, inventories, commodities
          </span>
        </div>
        <span className="fr-sigboard-toggle" aria-hidden="true">
          {open ? '–' : '+'}
        </span>
      </button>
      {open && (
        <div className="fr-sigboard-body">
          <ul className="fr-sigboard-list">
            {sig.map((s) => {
              const up = s.our_zscore > 0;
              const strong = Math.abs(s.our_zscore) >= 3;
              const isOpen = openId === s.id;
              return (
                <li key={s.id} className="fr-sig-item">
                  <button
                    type="button"
                    className="fr-sig"
                    onClick={() => setOpenId((id) => (id === s.id ? null : s.id))}
                    aria-expanded={isOpen}
                  >
                    <span className={`fr-sig-z ${up ? 'up' : 'down'} ${strong ? 'strong' : ''}`}>
                      {up ? '▲' : '▼'} {up ? '+' : ''}
                      {s.our_zscore.toFixed(1)}σ
                    </span>
                    <span className="fr-sig-name">{s.name}</span>
                    <span className="fr-sig-fam">{FAMILY_LABEL[s.family] || s.family}</span>
                    <span className="fr-sig-caret" aria-hidden="true">
                      {isOpen ? '–' : '+'}
                    </span>
                  </button>
                  {isOpen && <SignalTrace s={s} />}
                </li>
              );
            })}
          </ul>
          <div className="fr-sigboard-foot">
            measured monthly z-scores · FDR-controlled · association only, never a cause or a
            forecast
          </div>
        </div>
      )}
    </section>
  );
}
