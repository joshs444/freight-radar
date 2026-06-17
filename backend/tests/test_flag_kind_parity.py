"""Parity gate: the flag `kind` strings agree across the two-language boundary.

The one real value duplication F3 leaves hand-written: the detector produces flag `kind`
strings (the SSOT is ``detect.detectors.FLAG_KINDS``), and the frontend switches on those
exact strings to colour + legend + sub-toggle them (``frontend/src/lib/colors.ts``
FLAG_CATEGORIES). If the backend adds a kind the frontend doesn't categorise, that flag
renders as an uncategorised grey "Other" with no legend row; if the frontend lists a kind
the backend never emits, it's dead config. This asserts the two sets are IDENTICAL.
"""

from __future__ import annotations

import re
from pathlib import Path

from freight_radar.detect.detectors import FLAG_KINDS

COLORS_TS = Path(__file__).resolve().parents[2] / "frontend" / "src" / "lib" / "colors.ts"


def _frontend_categorised_kinds() -> set[str]:
    """The kinds colors.ts maps into a FLAG_CATEGORIES entry (the legend/sub-toggle set)."""
    src = COLORS_TS.read_text()
    # grab every `kinds: [ ... ]` array body inside FLAG_CATEGORIES and union their strings
    bodies = re.findall(r"kinds:\s*\[([^\]]*)\]", src)
    kinds: set[str] = set()
    for body in bodies:
        kinds |= set(re.findall(r"'([^']+)'", body))
    return kinds


def test_flag_kinds_agree_backend_and_frontend() -> None:
    frontend = _frontend_categorised_kinds()
    assert frontend, "could not parse any flag kinds from colors.ts FLAG_CATEGORIES"
    assert frontend == FLAG_KINDS, (
        "flag kind drift across the backend/frontend boundary — "
        f"only in backend (frontend renders these as uncategorised 'Other'): {sorted(FLAG_KINDS - frontend)}; "
        f"only in frontend (dead config, backend never emits): {sorted(frontend - FLAG_KINDS)}"
    )
