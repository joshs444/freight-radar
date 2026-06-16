"""H1-G receipts — ONE shared publish step list, two drivers.

ADR-0005 claims the GitHub-Action path (``publish_static``) and the Temporal path
run identical steps. That drifted once: publish_static grew signal_pool /
claimed-vs-measured / substrate / scorecard / catalog steps no Temporal activity
ran, so a Temporal-driven publish shipped without signals_fdr.json (the Board's
authoritative file), the scorecard, or the store catalog. The fix is structural —
``PUBLISH_STEPS`` in publish.py is the single ordered registry both drivers
iterate — and these tests pin it so the drift class cannot recur silently.
"""

from __future__ import annotations

import inspect

from freight_radar import publish


def test_publish_steps_registry_names_and_order():
    """The registry covers every post-export step publish_static historically ran,
    in the same order. A new step belongs HERE (both drivers pick it up for free);
    adding it to one driver by hand is the bug this test exists to catch."""
    assert [name for name, _ in publish.PUBLISH_STEPS] == [
        "signal_pool",
        "claimed_vs_measured",
        "substrate",
        "scorecard",
        "catalog",
    ]


def test_run_publish_steps_runs_every_step_in_order(monkeypatch, tmp_path):
    calls: list[str] = []
    fake = tuple(
        (name, lambda db, out, n=name: calls.append(n)) for name, _ in publish.PUBLISH_STEPS
    )
    monkeypatch.setattr(publish, "PUBLISH_STEPS", fake)
    ran = publish.run_publish_steps(tmp_path / "fr.duckdb", tmp_path)
    assert calls == ran == [name for name, _ in fake]


def test_both_drivers_iterate_the_shared_registry():
    """publish_static AND the Temporal assemble activity call run_publish_steps —
    neither re-lists the steps by hand, so they cannot silently diverge."""
    from freight_radar.temporal import activities

    static_src = inspect.getsource(publish.publish_static)
    assemble_src = inspect.getsource(activities.assemble_snapshot)
    assert "run_publish_steps" in static_src
    assert "run_publish_steps" in assemble_src
    # the old divergence shape — a driver calling step writers directly — is gone
    for direct_call in ("write_signal_pool", "write_claimed_vs_measured",
                        "publish_substrate", "write_scorecard", "write_catalog"):
        assert direct_call not in static_src, f"{direct_call} bypasses PUBLISH_STEPS"
        assert direct_call not in assemble_src, f"{direct_call} bypasses PUBLISH_STEPS"
