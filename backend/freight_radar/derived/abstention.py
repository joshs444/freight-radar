"""The reasoner's pre-assertion screen — the gate that makes the abstention demo real.

Before any drafted assertion becomes a claim it passes ``screen()``, which fuses the two
honesty gates: the language firewall (causal/forecast prose is refused outright, even when it
cites a real layer) and ``ground_or_abstain`` (a draft with nothing the store can cite is
dropped). A bait prompt — a forecast, a causal attribution, a risk ranking, a phantom entity —
produces ZERO claims by construction. This is the falsifiable opposite of "a deterministic AI
predicts cascades 99.7%": an AI that *structurally cannot* fabricate, with a screen that proves it.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..honesty.lexicon import scan as scan_causal
from .contract import ABSTAIN, Claim, ground_or_abstain

BAIT_PATH = Path(__file__).parent / "bait.jsonl"


def load_baits() -> list[dict]:
    """The living abstention battery (forecast / causal / risk-ranking / phantom-entity)."""
    return [json.loads(ln) for ln in BAIT_PATH.read_text().splitlines() if ln.strip()]


def battery_result(out_dir=None) -> dict:
    """Run the whole battery: every bait MUST refuse. Returns a scorecard-ready summary."""
    baits = load_baits()
    survived = [b["prompt"] for b in baits if screen(b["prompt"], [b["needs_layer"]], out_dir=out_dir)]
    return {"baits": len(baits), "refused": len(baits) - len(survived), "all_refused": not survived}


def screen(prompt: str, cites, *, out_dir=None) -> Claim | None:
    """Return an admissible Claim, or None if the draft is REFUSED. Refusal fires when the
    text carries causal/forecast language (the firewall) OR nothing grounds it (abstain)."""
    if scan_causal(prompt):
        return None  # REFUSED by the language firewall — causal/forecast prose
    claim = ground_or_abstain(prompt, cites, out_dir=out_dir)
    if claim is ABSTAIN:
        return None  # REFUSED — no measured observation to cite
    return claim


def refusal_reason(prompt: str, cites, *, out_dir=None) -> str | None:
    """The human-readable reason a draft was refused, or None if it's admissible."""
    hits = scan_causal(prompt)
    if hits:
        return f"language firewall: causal/forecast term {hits}"
    if ground_or_abstain(prompt, cites, out_dir=out_dir) is ABSTAIN:
        return "abstained: no measured observation in the store supports this"
    return None
