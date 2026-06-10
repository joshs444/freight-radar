"""The DERIVED briefing — the reasoner's output + its honesty gates (P6 capstone).

The reasoner is **offline and deterministic**: a ``python -m`` step (reason.py — fixed
templates, no model in the loop) reads the published store and writes ``ai_briefing.json`` on
the weekly cadence; the static site only *serves* it, so the live cost is **zero** — no LLM is
ever called anywhere. This module is the VALIDATOR (not a runtime model call): it enforces, in
CI, the exact firewall the plan demands of a non-deterministic reasoner, so a model could only
ever be wired in BEHIND these gates —

  * **grounded** — every claim cites ≥1 layer that exists in the store (zero cites = fail, the
    same gate the human chat already passes);
  * **association-only** — no causal/forecast verb in any claim (the shared honesty lexicon);
  * **DERIVED, metric-null** — it is commentary the store *quotes*, never a number it owns;
  * **labeled** — stamped with the agent_model that said it.

It imports nothing from the fact path; nothing in the fact path imports it (test_derived +
test_layer_firewall prove the quarantine). So the reasoner reads everything (leverage) but
every utterance is cited, association-only, and physically unable to corrupt the store (honesty).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..honesty.lexicon import scan as scan_causal

# Fixed process-boilerplate keys the agent does NOT author as a claim — they legitimately use
# the banned words in negation ("co-occurrence is association, never causation"; the `method`
# string describes that the agent never forecasts). Everything ELSE is treated as agent prose
# and scanned. Adding an agent-authored field (a summary, a headline) is therefore caught by
# default — the rendered firewall is FAIL-CLOSED, not an allowlist of what to check.
_BOILERPLATE_KEYS = frozenset(
    {"tier", "metric", "agent_model", "generated_at", "as_of", "method", "disclaimer", "cites"}
)


def scan_rendered(briefing: dict) -> list[str]:
    """Scan every AGENT-AUTHORED string in the rendered briefing for causal/forecast language —
    not only ``claims[].text``. A causal verb that drifts into any new free-text field (a
    headline, a summary, a per-claim rationale) fails here, even though the structured
    claim-text check would miss it. Fixed boilerplate keys are skipped (they negate the words
    by design); any unknown key IS scanned (fail-closed)."""
    out: list[str] = []

    def walk(obj: object, path: str) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k in _BOILERPLATE_KEYS:
                    continue
                walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")
        elif isinstance(obj, str):
            hits = scan_causal(obj)
            if hits:
                out.append(f"{path}: causal/forecast language {hits} in agent prose")

    walk(briefing, "briefing")
    return out


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
        cites = c.get("cites") or []
        if not cites:
            out.append(f"claim {i}: zero cites — every claim must trace to the store")
        for cite in cites:
            if cite not in valid_layer_ids:
                out.append(f"claim {i}: cite {cite!r} is not a layer in the store")

    # the rendered language firewall: causal/forecast language in ANY agent-authored field,
    # not just claim text (a summary/headline that drifts to "amid escalating" fails here too)
    out.extend(scan_rendered(briefing))
    return out


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text())
