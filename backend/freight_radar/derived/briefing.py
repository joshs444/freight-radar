"""The AI briefing — the DERIVED reasoner's output + its honesty gates (P6 capstone).

The reasoner is **offline**: Claude Code (the Agent SDK) reads the published store and writes
``ai_briefing.json`` on the weekly cadence; the static site only *serves* it, so the live cost
is **zero** — no LLM is ever called on a page-view. This module is the VALIDATOR (not a runtime
model call): it enforces, in CI, the exact firewall the plan demands of a non-deterministic
reasoner —

  * **grounded** — every claim cites ≥1 layer that exists in the store (zero cites = fail, the
    same gate the human chat already passes);
  * **association-only** — no causal/forecast verb in any claim (the shared honesty lexicon);
  * **DERIVED, metric-null** — it is commentary the store *quotes*, never a number it owns;
  * **labeled** — stamped with the agent_model that said it.

It imports nothing from the fact path; nothing in the fact path imports it (test_derived +
test_layer_firewall prove the quarantine). So the agent reasons over everything (leverage) but
every utterance is cited, association-only, and physically unable to corrupt the store (honesty).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..honesty.lexicon import scan as scan_causal


def validate(briefing: dict, valid_layer_ids: set[str]) -> list[str]:
    """Return a list of honesty violations (empty == the briefing is admissible)."""
    out: list[str] = []
    if briefing.get("tier") != "DERIVED":
        out.append(f"tier must be DERIVED, got {briefing.get('tier')!r}")
    if briefing.get("metric") is not None:
        out.append("DERIVED owns no metric — 'metric' must be null/absent")
    if not briefing.get("agent_model"):
        out.append("missing agent_model (a DERIVED claim must say who said it)")

    claims = briefing.get("claims") or []
    if not claims:
        out.append("a briefing with no claims is not a briefing")
    for i, c in enumerate(claims):
        text = str(c.get("text", ""))
        cites = c.get("cites") or []
        if not cites:
            out.append(f"claim {i}: zero cites — every claim must trace to the store")
        for cite in cites:
            if cite not in valid_layer_ids:
                out.append(f"claim {i}: cite {cite!r} is not a layer in the store")
        hits = scan_causal(text)
        if hits:
            out.append(f"claim {i}: causal/forecast verb {hits} — association-only")
    return out


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text())
