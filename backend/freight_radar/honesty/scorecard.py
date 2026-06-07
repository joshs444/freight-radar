"""The acceptance harness's scorecard (Layer 4) — minimal start.

Computes the honesty metrics that already compute deterministically from the registry +
predicates and writes ``scoreboard.json``. It tracks "are we improving?" over time and
is **never a ship gate** (correct != improving — you ship on the binary CI gates, the
scorecard only tells you where to invest). It grows one row per phase.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from ..registry.layers import REGISTRY
from . import predicates as P


def build_scorecard() -> dict:
    tiers = Counter(d.kind.value for d in REGISTRY)
    gates = {
        "tier_predicates": not P.tier_violations(),
        "causal_verb_lexicon": not P.causal_copy_violations(),
        "zero_cost": not P.cost_violations(),
        "source_completeness": not P.source_completeness_violations(),
        "source_coverage": not P.source_coverage_violations(),
    }
    cov = P.source_coverage()
    return {
        "layers_total": len(REGISTRY),
        "layers_by_tier": {k: tiers.get(k, 0) for k in ("SPINE", "SIGNAL", "CONTEXT", "DERIVED")},
        "globe_layers": sum(1 for d in REGISTRY if d.globe is not None),
        "honesty_gates": gates,
        "honesty_ci_pass_rate": round(100 * sum(gates.values()) / len(gates), 1),
        "zero_cost_compliance_pct": 100.0 if gates["zero_cost"] else 0.0,
        "source_coverage_pct": cov["pct"],
        "note": (
            "Binary CI gates decide shipping; this scorecard tracks trend only "
            "(correct != improving). Grows one row per phase."
        ),
    }


def write(out_dir: Path) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    p = out_dir / "scoreboard.json"
    card = build_scorecard()
    card["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    p.write_text(json.dumps(card, indent=2) + "\n")
    return p


if __name__ == "__main__":
    from ..config import publish_dir

    out = write(publish_dir())
    print(f"wrote {out}")
    print(json.dumps(build_scorecard(), indent=2))
