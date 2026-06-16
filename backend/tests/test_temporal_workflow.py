"""Wave 3 receipts — run the durable workflow for real on the time-skipping
test server (no Docker, no CLI), and prove the dedup ledger + retry behavior.

  * test_pipeline_end_to_end    : workflow runs all 5 stages, publishes a
                                  versioned manifest + snapshot + flags.
  * test_dedup_free_rerun       : a 2nd identical run makes ZERO attribution calls.
  * test_activity_retries       : RetryPolicy re-drives a transient failure
                                  (the same durability that makes kill->restart resume).

Requires the populated DuckDB from `python -m freight_radar.backfill`; skipped if
absent (CI runs the detector unit tests instead).
"""

from __future__ import annotations

import shutil
import uuid

import pytest
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from freight_radar.config import DEFAULT_DB_PATH
from freight_radar.temporal.activities import ALL_ACTIVITIES
from freight_radar.temporal.workflow import FreightRadarWorkflow
from tests.retry_probe import RetryProbeWorkflow, flaky_activity, reset

pytestmark = pytest.mark.skipif(
    not DEFAULT_DB_PATH.exists(),
    reason="needs a populated DuckDB (run: python -m freight_radar.backfill)",
)

TASK_QUEUE = "test-fr"


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    """Point the activities at a temp copy of the DuckDB + a temp publish dir,
    so the workflow never touches the real repo files (and the ledger is fresh)."""
    db = tmp_path / "fr.duckdb"
    shutil.copy(DEFAULT_DB_PATH, db)
    pub = tmp_path / "data"
    pub.mkdir()
    monkeypatch.setenv("FREIGHT_RADAR_DB", str(db))
    monkeypatch.setenv("FREIGHT_RADAR_PUBLISH_DIR", str(pub))
    return {"db": db, "pub": pub}


async def _run(client, params):
    async with Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[FreightRadarWorkflow],
        activities=ALL_ACTIVITIES,
    ):
        return await client.execute_workflow(
            FreightRadarWorkflow.run,
            params,
            id=f"wf-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )


async def test_pipeline_end_to_end(isolated_env):
    async with await WorkflowEnvironment.start_time_skipping() as env:
        result = await _run(env.client, {"skip_fetch": True})

    assert set(result) >= {"detect", "attribute", "assemble", "publish"}
    assert result["detect"]["n_flags"] >= 1
    assert result["publish"]["version"] == 1
    assert result["publish"]["flag_count"] == result["detect"]["n_flags"]

    pub = isolated_env["pub"]
    for f in ("snapshot.json", "flags.json", "manifest.json"):
        assert (pub / f).exists(), f"{f} was not published"

    # H1-G: the durable driver must run the SAME PUBLISH_STEPS publish_static does. The step
    # list the assemble activity reports proves every step RAN (a regression dropping
    # run_publish_steps makes this key absent -> KeyError); we then anchor it behaviorally on
    # the two UNCONDITIONAL outputs that must land in the durable path's dir. signals_fdr.json
    # / claimed_vs_measured.json are deliberately NOT asserted as files — they are written
    # conditionally (no signal family / stress-dependent), so existence is DB-content-dependent;
    # the step-list assertion is what guards that signal_pool & claimed_vs_measured ran.
    from freight_radar import publish

    assert result["assemble"]["publish_steps"] == [name for name, _ in publish.PUBLISH_STEPS]
    for f in ("scoreboard.json", "store/catalog.json"):
        assert (pub / f).exists(), f"{f} (an unconditional PUBLISH_STEPS output) missing on the Temporal path"


async def test_dedup_free_rerun(isolated_env):
    async with await WorkflowEnvironment.start_time_skipping() as env:
        first = await _run(env.client, {"skip_fetch": True})
        second = await _run(env.client, {"skip_fetch": True})

    # first run attributes the new flags; second run finds them all in the ledger
    assert first["attribute"]["new_attributions"] >= 1
    assert second["attribute"]["new_attributions"] == 0
    assert second["attribute"]["llm_calls"] == 0
    # version still bumps each publish (the loop ran twice)
    assert second["publish"]["version"] == 2


# --- retry / durability probe (self-contained, no DuckDB) ------------------
async def test_activity_retries_then_succeeds():
    reset()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue="test-retry",
            workflows=[RetryProbeWorkflow],
            activities=[flaky_activity],
        ):
            result = await env.client.execute_workflow(
                RetryProbeWorkflow.run, id=f"retry-{uuid.uuid4()}", task_queue="test-retry"
            )
    assert result == 3  # failed twice, succeeded on the 3rd attempt
