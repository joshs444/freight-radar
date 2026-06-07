"""derived/gate.py — the fail-closed honesty gate for the DERIVED reasoner (Step 7).

A briefing ships ONLY if every check passes — a conjunction, no warn-level, no override,
fail-closed (a missing sidecar / unparseable input counts as failure):

    validate       tier==DERIVED, metric null, every claim cites a real layer  +  the rendered
                   language firewall (zero causal/forecast tokens in any agent string)
    attribution    every NUMBER in a claim is ENTAILED by one of its cited layers — the value,
                   or the item-count, is verbatim in the cited data. String-decidable: a number
                   not found in its cites FAILS. There is NO llm-judge — *correctness is not
                   faithfulness*, so a claim whose number we can't string-match is rejected,
                   never escalated.
    abstention     the bait battery still refuses everything (a forecast/causal/rank/phantom
                   prompt yields zero claims) — the reasoner hasn't drifted.
    provenance     no cite resolves to a telemetry/engagement layer — the model was never shown
                   what got clicked, so it could not have optimized for it.

This runs BEFORE the briefing is written AND in CI over the committed artifact. It lives in
derived/ (quarantined): tests may import it; no fact-path module may.
"""

from __future__ import annotations

import re

from .. import store
from .abstention import battery_result
from .briefing import validate

_NUM = re.compile(r"-?\d+(?:\.\d+)?")
# a cite to any of these would mean the reasoner saw engagement data — there are none today,
# and this check is the structural guarantee there never can be one inside a DERIVED claim
_TELEMETRY = frozenset({"telemetry", "analytics", "clicks", "views", "engagement", "popularity"})


def _numbers(text: str) -> list[float]:
    text = re.sub(r"\d{4}-\d{2}-\d{2}", " ", text)  # an ISO date is a timestamp, not a claim
    out = []
    for m in _NUM.findall(text):
        try:
            out.append(float(m))
        except ValueError:
            pass
    return out


def _collect(payload: object, hay: set[float]) -> None:
    """Every number a claim could honestly cite: scalar values, numbers inside strings, AND
    the LENGTH of any list (a count — '271 ports flagged' is entailed by len(flags))."""
    if isinstance(payload, dict):
        for v in payload.values():
            _collect(v, hay)
    elif isinstance(payload, list):
        hay.add(float(len(payload)))
        for v in payload:
            _collect(v, hay)
    elif isinstance(payload, bool):
        return
    elif isinstance(payload, (int, float)):
        hay.add(round(float(payload), 4))
    elif isinstance(payload, str):
        for m in _NUM.findall(payload):
            try:
                hay.add(round(float(m), 4))
            except ValueError:
                pass


def _entailed(n: float, hay: set[float]) -> bool:
    # exact-ish: a tiny absolute tolerance (rounding) or 0.1% relative — never a fuzzy "close"
    return any(abs(n - h) <= 0.05 or (h != 0 and abs(n - h) / abs(h) <= 0.001) for h in hay)


def attribution_violations(briefing: dict, out_dir=None) -> list[str]:
    out: list[str] = []
    for i, c in enumerate(briefing.get("claims") or []):
        nums = _numbers(str(c.get("text", "")))
        if not nums:
            continue
        hay: set[float] = set()
        for cite in c.get("cites") or []:
            try:
                _collect(store.get_layer(cite, out_dir=out_dir).get("payload"), hay)
            except Exception:  # noqa: BLE001 — a bad cite is a failure, not a crash
                pass
        for n in nums:
            if not _entailed(n, hay):
                out.append(f"claim {i}: {n} is not entailed by its cites {c.get('cites')}")
    return out


def provenance_violations(briefing: dict) -> list[str]:
    out: list[str] = []
    for i, c in enumerate(briefing.get("claims") or []):
        for cite in c.get("cites") or []:
            if str(cite).lower() in _TELEMETRY:
                out.append(f"claim {i}: cites a telemetry layer {cite!r} — engagement-blind by law")
    return out


def gate_briefing(briefing: dict, valid_layer_ids: set[str], out_dir=None) -> dict:
    """Run the whole gate. Returns {check_name: [violations]} for each FAILING check (empty
    dict == the briefing ships). The reasoner calls this before writing; CI calls it over the
    committed artifact. Fail-closed: any non-empty value blocks."""
    checks = {
        "validate": validate(briefing, valid_layer_ids),  # tier/metric/cites + language firewall
        "attribution": attribution_violations(briefing, out_dir),
        "abstention": (
            []
            if battery_result(out_dir=out_dir)["all_refused"]
            else ["the abstention battery produced a claim — the reasoner drifted"]
        ),
        "provenance": provenance_violations(briefing),
    }
    return {k: v for k, v in checks.items() if v}
