"""Layer-2 acceptance (golden masters): the SPINE/SIGNAL sidecars are byte-identical
to the frozen masters in ``tests/golden/``.

This is what makes the P0 registry refactor *provably* a no-op on the numbers — any
drift in a computed value is an unblessed diff (red), not a silent regression. A
deliberate output change requires an explicit, reviewable re-bless:

    cd backend && uv run python -m tests.golden_harness bless

See tests/golden_harness.py and docs/plans/ACCEPTANCE-HARNESS.md (Layer 2).
"""

from __future__ import annotations

import difflib

import pytest

from tests.golden_harness import GOLDEN_DIR, GOLDEN_SIDECARS, capture


@pytest.fixture(scope="module")
def snapshots() -> dict[str, str]:
    # One offline pipeline run; the 11 parametrized cases each compare one sidecar.
    return capture()


@pytest.mark.parametrize("name", GOLDEN_SIDECARS)
def test_sidecar_matches_golden(name: str, snapshots: dict[str, str]) -> None:
    golden_path = GOLDEN_DIR / f"{name}.json"
    assert golden_path.exists(), (
        f"missing committed golden: {name}.json "
        "(run: cd backend && uv run python -m tests.golden_harness bless)"
    )
    expected = golden_path.read_text()
    actual = snapshots[name]
    if actual != expected:
        diff = "\n".join(
            difflib.unified_diff(
                expected.splitlines(),
                actual.splitlines(),
                fromfile=f"golden/{name}.json",
                tofile="current",
                lineterm="",
                n=2,
            )
        )
        pytest.fail(
            f"{name}.json drifted from its golden master:\n{diff[:4000]}\n\n"
            "If this change is intentional, re-bless: "
            "cd backend && uv run python -m tests.golden_harness bless"
        )
