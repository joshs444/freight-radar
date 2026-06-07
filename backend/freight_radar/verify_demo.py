"""The honest-no demo — an agent grounds every claim through ``store.verify()`` before it
speaks, and SUPPRESSES the ones the measured store can't back.

This is the runnable artifact behind the 5-year plan's most hireable demo: a consumer (here a
deterministic stand-in for an LLM agent; live, Claude Code calls the same thing via the
``verify`` MCP tool) refuses to assert anything the store doesn't measure. A grounded claim is
cited with full provenance; an ungrounded geopolitics/forecast claim is dropped with the honest
"no". The store never adjudicates — it returns a lineage lookup or abstains.

    python -m freight_radar.verify_demo [data_dir]
"""

from __future__ import annotations

import sys
from pathlib import Path

from .config import publish_dir
from .store import verify

# (the claim a consumer is "tempted" to assert, the store layer it would need, optional entity)
CANDIDATE_CLAIMS: tuple[tuple[str, str, str | None], ...] = (
    ("Global ocean-freight stress is at an elevated level right now.", "stress", None),
    ("There is a cited water-level reading at the Port of Charleston.", "tides", "Charleston"),
    ("A freight transport-cost anomaly is flagged across modes.", "freight_rate", None),
    ("GDACS is carrying official hazard alerts near the chain.", "disruptions", None),
    ("Geopolitical tensions are escalating in the Strait of Hormuz.", "geopolitical_tension", None),
    ("Conflict will disrupt the Suez Canal next week.", "forecast_disruption", None),
    ("The freight slowdown was caused by the recent earthquakes.", "causal_attribution", None),
)


def run(data_dir: Path) -> int:
    """Print a cite-or-suppress trace. Returns the number of suppressed (ungrounded) claims."""
    print("HONEST-NO GATE — every claim is grounded through the store before it is asserted.\n")
    suppressed = 0
    for claim, layer, entity in CANDIDATE_CLAIMS:
        r = verify(layer, entity, out_dir=data_dir)
        if r["grounded"]:
            src = (r.get("source") or {}).get("name") or "core measured spine"
            print(f"  ✓ CITED      {claim}")
            print(f"               ↳ grounded in '{r['layer']}' ({r['tier']}, as of {r['as_of']}) · {src}")
        else:
            suppressed += 1
            print(f"  ⊘ SUPPRESSED {claim}")
            print(f"               ↳ {r['reason']}")
    print(
        f"\n{suppressed}/{len(CANDIDATE_CLAIMS)} claims suppressed — the agent said only what the "
        "store can cite. The honest 'no' is the answer; the store never adjudicates a verdict."
    )
    return suppressed


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    data_dir = Path(args[0]) if args else publish_dir()
    run(data_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
