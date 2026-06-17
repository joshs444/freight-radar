"""Layer-1 invariants (registry parity): the generated TS can't drift from the Python
registry, and useData fetches exactly the files the registry declares.

These are the "TS id-set == Python id-set" gate the vision names (§4) plus a fetch-
manifest drift guard, so the registry stays the *single* source of truth: adding a
layer in registry/layers.py and forgetting to regenerate, or wiring a fetch into
useData.ts that the registry doesn't know about, both fail CI here.
"""

from __future__ import annotations

import re
from pathlib import Path

from freight_radar.registry.codegen import generated_type_names, render_ts, render_types_ts
from freight_radar.registry.layers import REGISTRY

REPO_ROOT = Path(__file__).resolve().parents[2]
GEN_TS = REPO_ROOT / "frontend" / "src" / "lib" / "layers.gen.ts"
TYPES_GEN_TS = REPO_ROOT / "frontend" / "src" / "types.gen.ts"
TYPES_TS = REPO_ROOT / "frontend" / "src" / "types.ts"
USE_DATA_TS = REPO_ROOT / "frontend" / "src" / "lib" / "useData.ts"


def test_generated_ts_is_current() -> None:
    """The committed layers.gen.ts is exactly what the registry renders (no hand-edit,
    no forgotten regenerate)."""
    assert GEN_TS.exists(), "layers.gen.ts is missing — run: uv run python -m freight_radar.registry.codegen"
    committed = GEN_TS.read_text()
    rendered = render_ts()
    assert committed == rendered, (
        "layers.gen.ts is stale or hand-edited. Regenerate:\n"
        "  cd backend && uv run python -m freight_radar.registry.codegen"
    )


def test_generated_types_ts_is_current() -> None:
    """The committed types.gen.ts is exactly what the shape registry renders (byte-identity)."""
    assert TYPES_GEN_TS.exists(), (
        "types.gen.ts is missing — run: uv run python -m freight_radar.registry.codegen"
    )
    assert TYPES_GEN_TS.read_text() == render_types_ts(), (
        "types.gen.ts is stale or hand-edited. Regenerate:\n"
        "  cd backend && uv run python -m freight_radar.registry.codegen"
    )


def test_types_ts_reexports_every_generated_interface() -> None:
    """types.ts must re-export exactly the interfaces types.gen.ts generates, so every
    `from '../types'` import keeps resolving (a generated interface that isn't re-exported,
    or a re-export that no longer exists, both fail here)."""
    reexported = set(re.findall(r"export type \{([^}]+)\} from '\./types\.gen\.ts'", TYPES_TS.read_text()))
    names: set[str] = set()
    for group in reexported:
        names |= {n.strip() for n in group.split(",")}
    assert names == set(generated_type_names()), (
        "types.ts re-exports drifted from types.gen.ts — "
        f"only generated: {set(generated_type_names()) - names}; only re-exported: {names - set(generated_type_names())}"
    )


def test_layerid_set_matches_python() -> None:
    """The TS LayerId union == the Python registry's globe layer ids (the named parity gate)."""
    ts = GEN_TS.read_text()
    union = re.search(r"export type LayerId =\n((?:\s*\|\s*'[^']+'\n?)+)", ts)
    assert union, "could not parse the LayerId union from layers.gen.ts"
    ts_ids = set(re.findall(r"'([^']+)'", union.group(1)))
    py_ids = {d.globe.layer_id for d in REGISTRY if d.globe is not None}
    assert ts_ids == py_ids, f"LayerId drift — only in TS: {ts_ids - py_ids}; only in Python: {py_ids - ts_ids}"


def test_usedata_drives_off_the_generated_manifest() -> None:
    """useData.ts loads its files by ITERATING the generated manifest, not a hand-kept list.

    The fetch set itself is gated by ``test_generated_ts_is_current`` (the byte-identical
    layers.gen.ts is rendered from REGISTRY, including CORE_FILES / OPTIONAL_SIDECAR_FILES /
    APPDATA_KEY_MAP). This gate keeps useData honest to THAT manifest: it must import the
    three generated exports and must NOT smuggle in a hardcoded `data/*.json` fetch list
    (the dead-codegen finding — the generated manifest existed but nothing consumed it)."""
    src = USE_DATA_TS.read_text()
    for name in ("CORE_FILES", "OPTIONAL_SIDECAR_FILES", "APPDATA_KEY_MAP"):
        assert name in src, f"useData.ts must import {name} from layers.gen.ts (drive off the manifest)"
    assert "layers.gen.ts" in src, "useData.ts must import the generated manifest"
    hardcoded = set(re.findall(r"data/[\w.]+\.json", src))
    assert not hardcoded, (
        f"useData.ts hardcodes a fetch list ({sorted(hardcoded)}) — it must iterate the "
        f"generated CORE_FILES / OPTIONAL_SIDECAR_FILES instead, so it can't drift from the registry"
    )
