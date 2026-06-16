"""Shared pytest guards — every test runs hermetically against throwaway state.

The committed ledgers under ``data/state/`` (ADR-0009) are production memory: a
local test run must never READ them (the golden masters and lifecycle labels
would drift with live history) or WRITE them (a test run is not a production
run). Every test therefore gets a fresh state dir through the same env override
the code honors (``ledger.state_dir()``); a test that needs a shared ledger
across steps sets its own.
"""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolated_state_dir(tmp_path_factory, monkeypatch):
    monkeypatch.setenv(
        "FREIGHT_RADAR_STATE_DIR", str(tmp_path_factory.mktemp("ledger-state"))
    )
