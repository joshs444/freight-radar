import { useCallback, useEffect, useState } from 'react';
import { getDB, loadStore, runQuery, VIEWS } from '../lib/duckdb.ts';

// "Query the store" — the agent-legible substrate, made touchable for humans. DuckDB-WASM
// runs SQL over the exact JSON sidecars the globe + the MCP server read, entirely in the
// browser (no backend). It's the visible proof of the P1.5 thesis: one clean, tier-stamped
// store that a machine — or a person with SQL — can reason across.

const EXAMPLES: { label: string; sql: string }[] = [
  {
    label: 'Store catalog — layers by tier',
    sql: 'SELECT kind, count(*) AS layers\nFROM layers\nGROUP BY kind\nORDER BY layers DESC;',
  },
  {
    label: 'Chokepoints under most pressure',
    sql: 'SELECT name, country, round(pct_change, 1) AS pct_change, round(zscore, 2) AS z\nFROM chokepoints\nORDER BY pct_change ASC\nLIMIT 12;',
  },
  {
    label: 'Active flags ⋈ their chokepoint',
    sql: 'SELECT f.entity, f.kind, f.severity, c.country\nFROM flags f\nJOIN chokepoints c ON f.portid = c.portid\nORDER BY f.severity DESC\nLIMIT 12;',
  },
  {
    label: 'Cited earthquakes (context), strongest',
    sql: 'SELECT round(mag, 1) AS mag, place, time\nFROM quakes\nORDER BY mag DESC\nLIMIT 12;',
  },
];

export default function StoreQuery() {
  const [status, setStatus] = useState(
    'Loading the in-browser SQL engine (DuckDB-WASM, one-time)…'
  );
  const [ready, setReady] = useState(false);
  const [views, setViews] = useState<string[]>([]);
  const [sql, setSql] = useState(EXAMPLES[0].sql);
  const [cols, setCols] = useState<string[]>([]);
  const [rows, setRows] = useState<unknown[][]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  const exec = useCallback(async (q: string) => {
    setErr(null);
    setRunning(true);
    try {
      const res = await runQuery(await getDB(), q);
      setCols(res.cols);
      setRows(res.rows);
    } catch (e) {
      setErr(String((e as Error).message || e));
    } finally {
      setRunning(false);
    }
  }, []);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const db = await getDB();
        const loaded = await loadStore(db, import.meta.env.BASE_URL || '/');
        if (!alive) return;
        setViews(loaded);
        setReady(true);
        setStatus(
          `Ready — ${loaded.length} tables loaded. Queries run entirely in your browser; nothing is sent to a server.`
        );
        await exec(EXAMPLES[0].sql);
      } catch (e) {
        if (alive) {
          setErr(String((e as Error).message || e));
          setStatus('Could not load the in-browser SQL engine.');
        }
      }
    })();
    return () => {
      alive = false;
    };
  }, [exec]);

  return (
    <div className="fr-query" data-ready={ready ? '1' : '0'}>
      <div className="fr-query-head">
        <h2>Query the store</h2>
        <p className="fr-query-sub">{status}</p>
      </div>
      <div className="fr-query-body">
        <aside className="fr-query-side">
          <div className="fr-query-side-h">Examples</div>
          {EXAMPLES.map((e) => (
            <button
              key={e.label}
              type="button"
              className="fr-query-ex"
              onClick={() => {
                setSql(e.sql);
                exec(e.sql);
              }}
            >
              {e.label}
            </button>
          ))}
          <div className="fr-query-side-h">Tables</div>
          <ul className="fr-query-views">
            {VIEWS.filter((v) => views.includes(v.view)).map((v) => (
              <li key={v.view}>
                <code>{v.view}</code>
                <span>{v.note}</span>
              </li>
            ))}
          </ul>
        </aside>
        <div className="fr-query-main">
          <textarea
            className="fr-query-sql"
            value={sql}
            onChange={(e) => setSql(e.target.value)}
            spellCheck={false}
            aria-label="SQL query"
          />
          <div className="fr-query-actions">
            <button
              type="button"
              className="fr-query-run"
              onClick={() => exec(sql)}
              disabled={!ready || running}
            >
              {running ? 'Running…' : 'Run ▸'}
            </button>
            {err && <span className="fr-query-err">{err}</span>}
          </div>
          <div className="fr-query-results" role="region" aria-label="Query results">
            <table data-testid="fr-query-table">
              <thead>
                <tr>
                  {cols.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i}>
                    {r.map((v, j) => (
                      <td key={j}>{v == null ? '' : String(v)}</td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="fr-query-count">
              {rows.length} rows · read-only · the same store the globe + the agents read
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
