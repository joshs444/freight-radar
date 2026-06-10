import { useEffect, useState } from 'react';

// The registry catalog (data/store/catalog.json) as the single runtime SSOT for provenance — the
// same catalog SourceLedger renders and an agent reads via MCP, now also feeding the <Trace>
// primitive everywhere on the site. Fetched ONCE (module-cached promise) and shared across every
// Trace instance, so a flag, a signal, an unflagged port, and a context dot all resolve their
// cited source the SAME way the backend does — by walking derives_from to the root.

export interface CatalogSource {
  name: string;
  url: string;
  license: string;
  auth?: string;
  cost?: string;
}
export interface CatalogLayer {
  id: string;
  kind: string; // SPINE | SIGNAL | CONTEXT | DERIVED
  producer: string;
  metric: string | null;
  sidecar: string | null;
  globe_layer?: string | null;
  derives_from: string | null;
  contract_monitored?: boolean;
  source: CatalogSource | null;
  honesty_note: string | null;
}
export interface Catalog {
  schema_version?: number;
  description?: string;
  counts: { layers: number; by_tier: Record<string, number> };
  layers: CatalogLayer[];
}

// The epistemic tier per registry kind — lifted from SourceLedger so the ledger and every Trace
// label a layer's tier identically. cls maps to the swatch colour classes in styles.css.
export const TIER: Record<string, { label: string; cls: string }> = {
  SPINE: { label: 'measured · spine', cls: 'spine' },
  SIGNAL: { label: 'measured · signal', cls: 'signal' },
  CONTEXT: { label: 'cited · context', cls: 'context' },
  DERIVED: { label: 'derived · templated', cls: 'derived' },
};

export interface EffectiveSource {
  source: CatalogSource | null; // the cited ROOT source, found by walking derives_from
  rootId: string | null;
  tier: { label: string; cls: string } | null; // resolved per-LAYER, NOT inherited from the root
  kind: string | null;
  metric: string | null;
  honestyNote: string | null;
}

const EMPTY: EffectiveSource = {
  source: null,
  rootId: null,
  tier: null,
  kind: null,
  metric: null,
  honestyNote: null,
};

// Walk derives_from to the provenance root for the cited Source (URL/name/license), but resolve
// the TIER from the layer itself (fence #6: a chokepoint's z-score is computed while a port's
// vessel count is raw — same root, different tier). Mirrors backend registry.root_source exactly.
export function effectiveSource(
  catalog: Catalog | null | undefined,
  layerId: string
): EffectiveSource {
  if (!catalog) return EMPTY;
  const byId = new Map(catalog.layers.map((l) => [l.id, l]));
  const self = byId.get(layerId);
  if (!self) return EMPTY;
  const seen = new Set<string>();
  let cur: CatalogLayer | undefined = self;
  let rootSource: CatalogSource | null = null;
  let rootId: string | null = null;
  while (cur && !seen.has(cur.id)) {
    seen.add(cur.id);
    if (cur.source) {
      rootSource = cur.source;
      rootId = cur.id;
      break;
    }
    cur = cur.derives_from ? byId.get(cur.derives_from) : undefined;
  }
  return {
    source: rootSource,
    rootId,
    tier: TIER[self.kind] ?? { label: self.kind, cls: '' },
    kind: self.kind,
    metric: self.metric,
    honestyNote: self.honesty_note,
  };
}

// One shared fetch for the whole app — the browser HTTP-caches the URL too, but the module promise
// guarantees a single in-flight request no matter how many Trace cards mount at once.
let _catalogPromise: Promise<Catalog | null> | null = null;
export function loadCatalog(): Promise<Catalog | null> {
  if (!_catalogPromise) {
    const base = import.meta.env.BASE_URL || '/';
    _catalogPromise = fetch(base + 'data/store/catalog.json')
      .then((r) => (r.ok ? (r.json() as Promise<Catalog>) : null))
      .catch(() => null);
  }
  return _catalogPromise;
}

export function useCatalog(): Catalog | null {
  const [cat, setCat] = useState<Catalog | null>(null);
  useEffect(() => {
    let alive = true;
    loadCatalog().then((c) => {
      if (alive) setCat(c);
    });
    return () => {
      alive = false;
    };
  }, []);
  return cat;
}
