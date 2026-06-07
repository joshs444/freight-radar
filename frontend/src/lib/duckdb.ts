// In-browser SQL over the published store, via DuckDB-WASM. Everything here runs in a
// Web Worker in the user's browser — no backend, nothing sent to a server. The engine is
// loaded from the free jsDelivr CDN (zero marginal cost; nothing 35MB ships in our deploy)
// using the documented cross-origin blob-worker shim. The data it queries is exactly the
// JSON sidecars the globe + the agents read, exposed as SQL views.

// Type-only import (erased at build) so the heavy duckdb-wasm JS isn't pulled into the
// boot-critical vendor chunk; the runtime module is dynamically imported in getDB(), so it
// (and the ~35MB wasm) only loads when someone actually opens the Data view.
import type { AsyncDuckDB } from '@duckdb/duckdb-wasm';

let _db: Promise<AsyncDuckDB> | null = null;

export function getDB(): Promise<AsyncDuckDB> {
  if (_db) return _db;
  _db = (async () => {
    const duckdb = await import('@duckdb/duckdb-wasm');
    const bundle = await duckdb.selectBundle(duckdb.getJsDelivrBundles());
    // cross-origin worker: wrap the CDN worker in a same-origin blob (the documented shim)
    const workerUrl = URL.createObjectURL(
      new Blob([`importScripts("${bundle.mainWorker}");`], { type: 'text/javascript' })
    );
    const worker = new Worker(workerUrl);
    const db = new duckdb.AsyncDuckDB(new duckdb.ConsoleLogger(duckdb.LogLevel.WARNING), worker);
    await db.instantiate(bundle.mainModule, bundle.pthreadWorker);
    URL.revokeObjectURL(workerUrl);
    return db;
  })();
  return _db;
}

export interface ViewDef {
  view: string;
  file: string;
  sql: string;
  note: string;
}

// The sidecars exposed as SQL views. Nested arrays are unnested into rows so an analyst
// (or an agent) can JOIN across the measured spine and the cited context ring directly.
export const VIEWS: ViewDef[] = [
  {
    view: 'layers',
    file: 'store/catalog.json',
    sql: "CREATE OR REPLACE VIEW layers AS SELECT unnest(layers, recursive := true) FROM read_json_auto('store/catalog.json')",
    note: 'the store catalog — every layer + its tier/source',
  },
  {
    view: 'chokepoints',
    file: 'snapshot.json',
    sql: "CREATE OR REPLACE VIEW chokepoints AS SELECT unnest(chokepoints, recursive := true) FROM read_json_auto('snapshot.json')",
    note: 'the 28 measured chokepoints (SPINE)',
  },
  {
    view: 'ports',
    file: 'snapshot.json',
    sql: "CREATE OR REPLACE VIEW ports AS SELECT unnest(ports, recursive := true) FROM read_json_auto('snapshot.json')",
    note: 'the measured ports (SPINE)',
  },
  {
    view: 'flags',
    file: 'flags.json',
    sql: "CREATE OR REPLACE VIEW flags AS SELECT * FROM read_json_auto('flags.json')",
    note: 'active disruption flags (SPINE)',
  },
  {
    view: 'quakes',
    file: 'quakes.json',
    sql: "CREATE OR REPLACE VIEW quakes AS SELECT unnest(items, recursive := true) FROM read_json_auto('quakes.json')",
    note: 'USGS M4+ earthquakes (CONTEXT — cited, association only)',
  },
  {
    view: 'news',
    file: 'news_geo.json',
    sql: "CREATE OR REPLACE VIEW news AS SELECT unnest(items, recursive := true) FROM read_json_auto('news_geo.json')",
    note: 'GDELT geo-news dots (CONTEXT — cited, association only)',
  },
  {
    view: 'commodities',
    file: 'commodities.json',
    sql: "CREATE OR REPLACE VIEW commodities AS SELECT unnest(items, recursive := true) FROM read_json_auto('commodities.json')",
    note: 'commodity anomalies — OUR 12-mo z-score, FDR-gated (SIGNAL)',
  },
  {
    view: 'streamflow',
    file: 'streamflow.json',
    sql: "CREATE OR REPLACE VIEW streamflow AS SELECT unnest(items, recursive := true) FROM read_json_auto('streamflow.json')",
    note: 'river stage on the Mississippi/Ohio freight corridor (CONTEXT)',
  },
  {
    view: 'space_weather',
    file: 'space_weather.json',
    sql: "CREATE OR REPLACE VIEW space_weather AS SELECT unnest(items, recursive := true) FROM read_json_auto('space_weather.json')",
    note: 'observed planetary K-index readings, NOAA SWPC (CONTEXT)',
  },
  {
    view: 'eonet',
    file: 'eonet.json',
    sql: "CREATE OR REPLACE VIEW eonet AS SELECT unnest(items, recursive := true) FROM read_json_auto('eonet.json')",
    note: 'open natural events — fire/volcano/storm/ice, NASA EONET (CONTEXT)',
  },
  {
    view: 'marine',
    file: 'marine.json',
    sql: "CREATE OR REPLACE VIEW marine AS SELECT unnest(items, recursive := true) FROM read_json_auto('marine.json')",
    note: 'model wave height at major chokepoints, Open-Meteo (CONTEXT)',
  },
  {
    view: 'macro',
    file: 'macro.json',
    sql: "CREATE OR REPLACE VIEW macro AS SELECT unnest(items, recursive := true) FROM read_json_auto('macro.json')",
    note: 'freight/industrial anomalies — OUR 12-mo z, FDR-gated (SIGNAL)',
  },
  {
    view: 'metals',
    file: 'metals.json',
    sql: "CREATE OR REPLACE VIEW metals AS SELECT unnest(items, recursive := true) FROM read_json_auto('metals.json')",
    note: 'metals/bulk-energy anomalies — OUR 12-mo z, FDR-gated (SIGNAL)',
  },
  {
    view: 'tides',
    file: 'tides.json',
    sql: "CREATE OR REPLACE VIEW tides AS SELECT unnest(items, recursive := true) FROM read_json_auto('tides.json')",
    note: 'observed water level at major US ports, NOAA CO-OPS (CONTEXT)',
  },
];

/** Fetch the sidecars + register them as DuckDB views. Returns the views that loaded. */
export async function loadStore(db: AsyncDuckDB, base: string): Promise<string[]> {
  const con = await db.connect();
  const loaded: string[] = [];
  const fetched = new Set<string>();
  try {
    for (const v of VIEWS) {
      try {
        if (!fetched.has(v.file)) {
          const r = await fetch(base + 'data/' + v.file);
          if (!r.ok) continue;
          await db.registerFileText(v.file, await r.text());
          fetched.add(v.file);
        }
        await con.query(v.sql);
        loaded.push(v.view);
      } catch {
        /* skip a missing or oddly-shaped sidecar — the rest still load */
      }
    }
  } finally {
    await con.close();
  }
  return loaded;
}

export interface QueryResult {
  cols: string[];
  rows: unknown[][];
}

export async function runQuery(db: AsyncDuckDB, sql: string): Promise<QueryResult> {
  const con = await db.connect();
  try {
    const res = await con.query(sql);
    const cols = res.schema.fields.map((f) => f.name);
    const rows = res.toArray().map((r) => {
      const o = r.toJSON() as Record<string, unknown>;
      return cols.map((c) => {
        const v = o[c];
        return typeof v === 'bigint' ? Number(v) : v;
      });
    });
    return { cols, rows };
  } finally {
    await con.close();
  }
}
