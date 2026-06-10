# 7. The tier firewall + the registry as single source of truth

Status: Accepted
Date: 2026-06-09

## Context

The app ships ~34 layers in one UI, but epistemically they are not the same
kind of thing: **SPINE** (the freight chain we compute end-to-end from
PortWatch), **SIGNAL** (one scalar we compute over a cited series), **CONTEXT**
(someone else's cited value, shown as-is), **DERIVED** (the templated briefing
— commentary that owns no number). The product's brand is that those boundaries
hold: a context layer that could write a measured number, or a layer wearing a
"measured" badge it didn't earn, is the core failure mode — and both versions
of the code look almost identical in review.

The layer list itself also used to live in several hand-maintained places (the
enricher tuple list, the publish sidecar set, the TS toggle/fetch manifests),
which is exactly the kind of duplication that drifts.

## Decision

One dataclass registry (`backend/freight_radar/registry/layers.py`) is the
single source of truth: every layer is one `LayerDescriptor` stamped with its
kind, producer, module, sidecar, cited `Source`, honesty note, and — for SPINE
— the provenance edge `derives_from`. Everything else is **derived** from it:

- the enricher pipeline order and the publish manifest's sidecar set are
  comprehensions over `REGISTRY`, not parallel lists;
- the frontend's `LayerId` union, panel sections, defaults, and fetch manifest
  are generated TypeScript (`registry/codegen.py` → `layers.gen.ts`; a CI test
  fails on drift);
- the tier rules are executable predicates (`honesty/predicates.py`):
  CONTEXT/DERIVED may own no metric, SIGNAL must declare one, every external
  source must be free and complete, layer copy is scanned against the shared
  causal/forecast lexicon, and SPINE must form a single-rooted acyclic graph —
  exactly one measured root, so the measured tier cannot silently inflate;
- the firewall is an import-graph test (`tests/test_layer_firewall.py`): a
  SIGNAL/CONTEXT module whose transitive imports reach the detector or the
  fact-writers (`detect`/`ingest`/`wap`/`backfill`) fails CI, and nothing may
  import the quarantined `derived/` namespace;
- a provenance-parity deploy gate (`registry/parity.py`) asserts the
  `source_url`/`license` stamped into shipped data equals the registry root, so
  the catalog and the published files cannot fork.

## Consequences

- Adding a layer is one descriptor append; the pipeline order, manifest, TS
  types, panel, and Source Ledger row all follow. There is no second list to
  forget.
- Tier inflation and firewall breaches are CI failures, not review comments: a
  new SPINE layer must name its parent or it is rejected as a second root; a
  context layer that gains a metric, a causal phrase, or a forbidden import
  goes red.
- The kinds are deliberately coarse. The schematic `lanes` arcs ship inside the
  SPINE core export and stay there, carried by an explicit `honesty_note`
  ("illustrative, not a measurement") rather than a fifth tier — disclosure
  over taxonomy.
- Honest costs: the registry is one large file fronted by ~26 thin adapter
  functions; the generated TS is a committed artifact that must be regenerated
  on registry changes (CI catches drift, but it is a step); and the firewall is
  static import analysis — it proves a module *cannot reach* a fact-writer, not
  that its values are correct.
