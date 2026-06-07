"""Layer-1 invariant (the structural firewall) — the gating invariant of the whole plan.

A SIGNAL/CONTEXT layer may *read* the published flags (and a few attach an annotation
field), but it must never be able to *compute or mutate* a number: its code cannot
import the detector, the ingest fact-table writers, or the Write-Audit-Publish promoter.
This is the honesty brand made structural — a compile/CI fact, not a comment or a grep.
A malicious branch (a CONTEXT layer importing the detector) fails here.

The check is a static import-graph BFS over the first-party package: for each
non-SPINE descriptor we walk its module's transitive imports (top-level AND
function-level, so a lazy `from ..detect import run` is still caught) and assert none
land in the forbidden fact-writer namespaces. See STANDPOINT-VISION.md §4 + §10 and
ACCEPTANCE-HARNESS.md (Layer 1, tier firewall).
"""

from __future__ import annotations

import ast
from pathlib import Path

import freight_radar
from freight_radar.registry.layers import REGISTRY, Kind

PKG_ROOT = Path(freight_radar.__file__).resolve().parent
PKG_NAME = "freight_radar"

# Namespaces that compute or write the spine's numbers. A SIGNAL/CONTEXT layer that can
# reach any of these can, in principle, manufacture or mutate a fact — forbidden.
FORBIDDEN_PREFIXES = (
    "freight_radar.detect",  # the change-point / z-score detector that PRODUCES flags
    "freight_radar.ingest",  # the fact-table writers (portwatch, dims)
    "freight_radar.wap",  # Write-Audit-Publish fact promotion
    "freight_radar.backfill",  # writes historical facts
)


def _module_map() -> dict[str, Path]:
    """Every first-party module's dotted name -> file path (packages included)."""
    out: dict[str, Path] = {}
    for p in PKG_ROOT.rglob("*.py"):
        rel = p.relative_to(PKG_ROOT).with_suffix("")
        parts = list(rel.parts)
        if parts[-1] == "__init__":
            parts = parts[:-1]
        out[".".join([PKG_NAME, *parts]) if parts else PKG_NAME] = p
    return out


MODULES = _module_map()


def _resolve(pkg_of_module: str, level: int, mod: str | None, name: str) -> list[str]:
    """Resolve one imported symbol to candidate first-party module dotted-names."""
    if level == 0:
        base = mod or ""
        cands = [base, f"{base}.{name}"] if base else []
    else:
        parts = pkg_of_module.split(".")
        prefix = parts[: len(parts) - (level - 1)] if level > 1 else parts
        head = ".".join(prefix)
        if mod:
            cands = [f"{head}.{mod}", f"{head}.{mod}.{name}"]
        else:
            cands = [f"{head}.{name}"]
    return [c for c in cands if c in MODULES]


def _direct_imports(module_name: str) -> set[str]:
    """First-party modules `module_name` imports (top-level + inside functions)."""
    path = MODULES.get(module_name)
    if not path:
        return set()
    # the package this module lives in (for relative resolution)
    pkg = module_name if path.name == "__init__.py" else module_name.rsplit(".", 1)[0]
    tree = ast.parse(path.read_text(), filename=str(path))
    edges: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                edges.update(_resolve(pkg, node.level, node.module, alias.name))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name in MODULES:
                    edges.add(alias.name)
    return edges


def _reachable(start: str) -> set[str]:
    """Transitive first-party import closure of `start` (BFS)."""
    seen: set[str] = set()
    stack = [start]
    while stack:
        cur = stack.pop()
        for nxt in _direct_imports(cur):
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return seen


def _forbidden_reach(module_name: str) -> set[str]:
    return {
        m for m in _reachable(module_name) if m.startswith(FORBIDDEN_PREFIXES)
    }


# --- the firewall, per layer ------------------------------------------------
_NON_SPINE = [
    d for d in REGISTRY if d.kind in (Kind.SIGNAL, Kind.CONTEXT, Kind.DERIVED) and d.module
]


def test_no_signal_or_context_layer_reaches_the_factwriters() -> None:
    violations = {d.id: _forbidden_reach(d.module) for d in _NON_SPINE}  # type: ignore[arg-type]
    violations = {k: v for k, v in violations.items() if v}
    assert not violations, (
        "FIREWALL BREACH — a SIGNAL/CONTEXT layer can reach the detector / fact-writers "
        f"(it could manufacture or mutate a number): {violations}"
    )


def test_every_non_spine_layer_was_actually_checked() -> None:
    # guards against a silently-empty check (e.g., all modules misnamed -> nothing analyzed)
    assert len(_NON_SPINE) >= 8, f"expected the context/signal ring, got {len(_NON_SPINE)}"
    for d in _NON_SPINE:
        assert d.module in MODULES, f"{d.id}: declared module {d.module!r} not found in the package"


def test_nothing_imports_the_derived_namespace() -> None:
    # The AI firewall, reverse direction (the P6 capstone's load-bearing guarantee): no module
    # outside derived/ may import freight_radar.derived. The reasoner's DERIVED output can be
    # validated + served, but it can NEVER flow back into the store / the fact path.
    offenders = []
    for mod in MODULES:
        if mod.startswith("freight_radar.derived"):
            continue
        reach = _reachable(mod) | _direct_imports(mod)
        if any(m.startswith("freight_radar.derived") for m in reach):
            offenders.append(mod)
    assert not offenders, f"modules importing the quarantined derived namespace: {offenders}"


def test_hyp_cannot_reach_the_factwriters() -> None:
    # the ML association tier reads the published substrate Parquet — it must NEVER reach the
    # detector / ingest / wap, so a co-movement it mines can't leak back into a measured number.
    breach = {m: _forbidden_reach(m) for m in MODULES if m.startswith("freight_radar.hyp")}
    breach = {k: v for k, v in breach.items() if v}
    assert not breach, f"FIREWALL BREACH — hyp/ can reach the fact-writers: {breach}"


def test_nothing_imports_the_hyp_namespace() -> None:
    # hyp_* is quarantined DARK exactly like derived/: nothing in the package imports it. The
    # reasoner consumes its ARTIFACT (data/hyp/), never the module — so a mined association can
    # never become a dependency of the store, and a CI fact (not a comment) keeps it off-globe.
    offenders = []
    for mod in MODULES:
        if mod.startswith("freight_radar.hyp"):
            continue
        reach = _reachable(mod) | _direct_imports(mod)
        if any(m.startswith("freight_radar.hyp") for m in reach):
            offenders.append(mod)
    assert not offenders, f"modules importing the quarantined hyp namespace: {offenders}"


def test_the_analyzer_finds_real_edges() -> None:
    # sanity: the detector itself MUST reach the forbidden namespaces, or the BFS is broken
    # and the firewall would be falsely green.
    assert _forbidden_reach("freight_radar.detect.run_detection"), (
        "analyzer found no fact-writer imports from the detector — the import graph is broken"
    )


def test_the_firewall_has_teeth() -> None:
    # a synthetic CONTEXT module that imports the detector must be flagged by the resolver,
    # proving a malicious branch would fail CI (we don't commit the malicious module).
    edges = _resolve("freight_radar", level=1, mod="detect.run_detection", name="run")
    assert "freight_radar.detect.run_detection" in edges, (
        "resolver failed to catch a `from .detect.run_detection import run` — no teeth"
    )


def test_a_malicious_context_layer_would_fail_ci() -> None:
    # The vision's named scenario: a CONTEXT layer wired into the detector / fact-writers
    # MUST fail CI. We don't commit such a layer — we prove the gate that catches it. The
    # per-layer check is `_forbidden_reach(d.module)`; for a CONTEXT layer pointed at a
    # fact-writer it is non-empty, so test_no_signal_or_context_layer_reaches_the_factwriters
    # would go red. (Same machinery, applied to the adversarial case.)
    for factwriter in (
        "freight_radar.detect.run_detection",
        "freight_radar.wap",
        "freight_radar.ingest.portwatch",
    ):
        reach = _reachable(factwriter) | {factwriter}
        assert any(m.startswith(FORBIDDEN_PREFIXES) for m in reach), (
            f"a malicious CONTEXT layer on {factwriter} would slip the firewall"
        )
