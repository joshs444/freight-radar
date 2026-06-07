import { useEffect, useState } from 'react';

// The "show your work" page — renders the registry catalog (data/store/catalog.json) as a
// human-readable provenance ledger: every layer, its epistemic tier, its cited source +
// license, what it is (the owned metric for measured layers, the honesty note for context),
// and how fresh it is (from manifest.json). The same catalog an agent reads via MCP, made
// legible to a person. This IS the honesty brand, on one page.

interface Source {
  name: string;
  url: string;
  license: string;
}
interface Layer {
  id: string;
  kind: string;
  producer: string;
  metric: string | null;
  sidecar: string | null;
  source: Source | null;
  honesty_note: string | null;
}
interface Catalog {
  counts: { layers: number; by_tier: Record<string, number> };
  layers: Layer[];
}
interface Manifest {
  layers?: Record<string, { present: boolean; generated_at?: string }>;
}

const TIER: Record<string, { label: string; cls: string }> = {
  SPINE: { label: 'measured · spine', cls: 'spine' },
  SIGNAL: { label: 'measured · signal', cls: 'signal' },
  CONTEXT: { label: 'cited · context', cls: 'context' },
};
const ORDER = ['SPINE', 'SIGNAL', 'CONTEXT'];

function ageDays(iso?: string): string {
  if (!iso) return '—';
  const d = (Date.now() - new Date(iso).getTime()) / 86400000;
  if (d < 1) return 'today';
  if (d < 2) return '1 day';
  return `${Math.floor(d)} days`;
}

export default function SourceLedger() {
  const [cat, setCat] = useState<Catalog | null>(null);
  const [man, setMan] = useState<Manifest>({});
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const base = import.meta.env.BASE_URL || '/';
    Promise.all([
      fetch(base + 'data/store/catalog.json').then((r) => r.json() as Promise<Catalog>),
      fetch(base + 'data/manifest.json')
        .then((r) => r.json() as Promise<Manifest>)
        .catch(() => ({})),
    ])
      .then(([c, m]) => {
        setCat(c);
        setMan(m);
      })
      .catch((e: Error) => setErr(String(e.message || e)));
  }, []);

  if (err) return <div className="fr-ledger">Could not load the catalog: {err}</div>;
  if (!cat) return <div className="fr-ledger">Loading the source ledger…</div>;

  const layers = [...cat.layers].sort((a, b) => ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind));
  const bt = cat.counts.by_tier;

  return (
    <div className="fr-ledger">
      <div className="fr-ledger-head">
        <h2>Source ledger — show your work</h2>
        <p className="fr-ledger-sub">
          {cat.counts.layers} layers · {bt.SPINE} spine + {bt.SIGNAL} signal (measured) ·{' '}
          {bt.CONTEXT} cited context. Every number is computed in Python from a cited source;
          context is possibly-related, never a stated cause.
        </p>
      </div>
      <div className="fr-ledger-table">
        <table data-testid="fr-ledger-table">
          <thead>
            <tr>
              <th>layer</th>
              <th>tier</th>
              <th>source</th>
              <th>license</th>
              <th>what it is</th>
              <th>fresh</th>
            </tr>
          </thead>
          <tbody>
            {layers.map((l) => {
              const t = TIER[l.kind] ?? { label: l.kind, cls: '' };
              const stem = l.sidecar ? l.sidecar.replace('data/', '').replace('.json', '') : null;
              const mf = stem ? man.layers?.[stem] : undefined;
              const fresh = !l.sidecar ? 'core' : mf?.present ? ageDays(mf.generated_at) : 'absent';
              return (
                <tr key={l.id}>
                  <td>
                    <code>{l.id}</code>
                  </td>
                  <td>
                    <span className={`fr-tier ${t.cls}`}>{t.label}</span>
                  </td>
                  <td>
                    {l.source ? (
                      l.source.url ? (
                        <a href={l.source.url} target="_blank" rel="noreferrer">
                          {l.source.name}
                        </a>
                      ) : (
                        l.source.name
                      )
                    ) : (
                      '—'
                    )}
                  </td>
                  <td>{l.source?.license ?? '—'}</td>
                  <td className="fr-ledger-what">{l.metric ?? l.honesty_note ?? '—'}</td>
                  <td>{fresh}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
