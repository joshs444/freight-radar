"""Acceptance gate (P2-B): the shipped data's stamped provenance matches the registry SSOT.

The same checks run as a deploy-gate in the weekly refresh (freight_radar.registry.parity); this
makes them part of the deterministic CI suite too, so a divergence is red on every push — never a
silent ship. See freight_radar/registry/parity.py for the three invariants.
"""

from __future__ import annotations

import pytest

from freight_radar.config import REPO_ROOT
from freight_radar.registry import parity

DATA = REPO_ROOT / "frontend" / "public" / "data"


def test_provenance_parity_holds_on_shipped_data() -> None:
    if not (DATA / "flags.json").exists():
        pytest.skip("no shipped flags.json in the working tree")
    problems = parity.check(DATA)
    assert problems == [], "provenance parity violations:\n" + "\n".join(f"  - {p}" for p in problems)


def test_parity_catches_a_drifted_url(tmp_path) -> None:
    # a planted bad source_url must be caught — the gate is not vacuously green
    (tmp_path / "flags.json").write_text(
        '[{"flag_id": "x", "source_url": "https://evil.example", "license": "PortWatch terms"}]'
    )
    problems = parity.check(tmp_path)
    assert any("source_url" in p for p in problems), "gate failed to catch a drifted flag source_url"
