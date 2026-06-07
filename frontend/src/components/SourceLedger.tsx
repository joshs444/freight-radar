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
  contract_monitored?: boolean;
}
interface Catalog {
  counts: { layers: number; by_tier: Record<string, number> };
  layers: Layer[];
}
interface Manifest {
  layers?: Record<string, { present: boolean; generated_at?: string }>;
}
interface Scoreboard {
  honesty_gates?: Record<string, boolean>;
  honesty_ci_pass_rate?: number;
  zero_cost_compliance_pct?: number;
  source_coverage_pct?: number;
}
interface BriefingClaim {
  text: string;
  cites: string[];
}
interface Briefing {
  agent_model: string;
  disclaimer?: string;
  claims: BriefingClaim[];
}
interface Demotions {
  note?: string;
  demoted: { stem: string; violations: string[] }[];
}

const TIER: Record<string, { label: string; cls: string }> = {
  SPINE: { label: 'measured · spine', cls: 'spine' },
  SIGNAL: { label: 'measured · signal', cls: 'signal' },
  CONTEXT: { label: 'cited · context', cls: 'context' },
  DERIVED: { label: 'derived · AI', cls: 'derived' },
};
const ORDER = ['SPINE', 'SIGNAL', 'CONTEXT', 'DERIVED'];

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
  const [score, setScore] = useState<Scoreboard | null>(null);
  const [brief, setBrief] = useState<Briefing | null>(null);
  const [demo, setDemo] = useState<Demotions | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    const base = import.meta.env.BASE_URL || '/';
    Promise.all([
      fetch(base + 'data/store/catalog.json').then((r) => r.json() as Promise<Catalog>),
      fetch(base + 'data/manifest.json')
        .then((r) => r.json() as Promise<Manifest>)
        .catch(() => ({})),
      fetch(base + 'data/scoreboard.json')
        .then((r) => r.json() as Promise<Scoreboard>)
        .catch(() => null),
      fetch(base + 'data/ai_briefing.json')
        .then((r) => r.json() as Promise<Briefing>)
        .catch(() => null),
      // present only when the weekly metabolism quarantined a drifted feed to dark
      fetch(base + 'data/demotions.json')
        .then((r) => (r.ok ? (r.json() as Promise<Demotions>) : null))
        .catch(() => null),
    ])
      .then(([c, m, s, b, d]) => {
        setCat(c);
        setMan(m);
        setScore(s);
        setBrief(b);
        setDemo(d);
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
          context is possibly-related, never a stated cause. Feeds marked{' '}
          <span className="fr-ledger-mon">shape ✓</span> have their schema + liveness
          machine-checked every refresh — a drifted source fails the run, never ships silently.
        </p>
      </div>
      {demo && demo.demoted.length > 0 && (
        <div className="fr-ledger-demoted" data-testid="fr-ledger-demoted">
          <span className="fr-ledger-demoted-h">⤓ auto-demoted to dark this refresh</span>
          {demo.demoted.map((d) => (
            <span key={d.stem} className="fr-ledger-demoted-row" title={d.violations.join(' · ')}>
              <code>{d.stem}</code> failed its data contract — pulled rather than shown broken
            </span>
          ))}
          <span className="fr-ledger-demoted-m">
            Rot is loud: a feed that breaks its schema disappears, never silently misleads.
          </span>
        </div>
      )}
      {score?.honesty_gates && (
        <div className="fr-ledger-score" data-testid="fr-ledger-score">
          <span className="fr-ledger-score-h">honesty self-grade</span>
          {Object.entries(score.honesty_gates).map(([k, ok]) => (
            <span key={k} className={`fr-gate ${ok ? 'ok' : 'bad'}`} title={k}>
              {ok ? '✓' : '✗'} {k.replace(/_/g, ' ')}
            </span>
          ))}
          <span className="fr-ledger-score-m">
            CI {score.honesty_ci_pass_rate ?? '—'}% · zero-cost{' '}
            {score.zero_cost_compliance_pct ?? '—'}% · sources {score.source_coverage_pct ?? '—'}%
          </span>
        </div>
      )}
      {brief && brief.claims?.length > 0 && (
        <div className="fr-brief-derived" data-testid="fr-brief-derived">
          <div className="fr-brief-derived-h">
            <span className="fr-tier derived">derived · AI commentary</span>
            <span className="fr-brief-derived-by">{brief.agent_model}</span>
          </div>
          <ul className="fr-brief-claims">
            {brief.claims.map((c, i) => (
              <li key={i}>
                <span>{c.text}</span>{' '}
                {c.cites.map((cite) => (
                  <code key={cite} className="fr-cite">
                    {cite}
                  </code>
                ))}
              </li>
            ))}
          </ul>
          {brief.disclaimer && <p className="fr-brief-disc">{brief.disclaimer}</p>}
        </div>
      )}
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
                  <td>
                    {fresh}
                    {l.contract_monitored && (
                      <span
                        className="fr-ledger-mon"
                        title="Shape machine-checked every refresh by the upstream drift detector (schema + liveness)"
                      >
                        shape ✓
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
