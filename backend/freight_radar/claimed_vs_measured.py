"""Claimed vs measured — the falsifiable opposite of an unfalsifiable accuracy number.

centrum-ai.com claims a deterministic AI predicts supply-chain cascades with 99.7% accuracy.
Standpoint publishes no accuracy number and forecasts nothing — it shows the MEASURED value,
its method, and its date, and stops. This producer pairs the competitor's CITED claim (a
``method=external_claim`` row we display, never one we make) with the live measured Global
Ocean Freight Stress Index, so the contrast is always current and self-falsifying.
"""

from __future__ import annotations

import json
from pathlib import Path

CLAIMANT = {
    "claimant": "centrum-ai.com",
    "claim": "A deterministic AI predicts supply-chain cascades with 99.7% accuracy.",
    "claim_type": "forecast + accuracy",
    "tier": "CONTEXT",
    "method": "external_claim",  # a claim we CITE + display, never one we make
    "source_url": "https://centrum-ai.com",
}


def build(data_dir: Path) -> dict:
    data_dir = Path(data_dir)
    measured = None
    p = data_dir / "stress.json"
    if p.exists():
        try:
            s = json.loads(p.read_text())
        except (OSError, ValueError):
            s = None
        if isinstance(s, dict) and s.get("available") is not False and s.get("index") is not None:
            measured = {
                "layer": "stress",
                "what": "Global Ocean Freight Stress Index",
                "value": s.get("index"),
                "label": s.get("label"),
                "as_of": s.get("as_of") or s.get("generated_at"),
                "method": (
                    "a breadth+depth composite computed in Python from IMF PortWatch — "
                    "no model in the number path"
                ),
            }
    return {
        "note": (
            "What a black-box competitor CLAIMS vs what Standpoint MEASURES — the falsifiable "
            "opposite of an unfalsifiable accuracy number."
        ),
        **CLAIMANT,
        "measured": measured,
        "standpoint_says": (
            "We forecast nothing and publish no accuracy number. We show the measured value, its "
            "method, and its date — cited and falsifiable — and stop. Co-occurrence is "
            "association, never a cause."
        ),
    }


def write(data_dir: Path) -> Path:
    out = Path(data_dir)
    pth = out / "claimed_vs_measured.json"
    pth.write_text(json.dumps(build(out), indent=2) + "\n")
    return pth


def main(argv: list[str] | None = None) -> int:
    import sys

    from .config import publish_dir

    args = argv if argv is not None else sys.argv[1:]
    print(write(Path(args[0]) if args else publish_dir()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
