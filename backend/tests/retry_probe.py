"""A self-contained flaky activity + workflow for the retry/durability receipt.

Kept in its own module (imports ONLY temporalio) so the workflow sandbox can
import it cleanly — the test module imports non-deterministic libs at top level,
which the sandbox restricts.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

_attempts = {"n": 0}


def reset() -> None:
    _attempts["n"] = 0


@activity.defn
async def flaky_activity() -> int:
    _attempts["n"] += 1
    if _attempts["n"] < 3:
        raise RuntimeError(f"transient failure #{_attempts['n']}")
    return _attempts["n"]


@workflow.defn
class RetryProbeWorkflow:
    @workflow.run
    async def run(self) -> int:
        return await workflow.execute_activity(
            flaky_activity,
            start_to_close_timeout=timedelta(seconds=10),
            retry_policy=RetryPolicy(
                initial_interval=timedelta(seconds=1), maximum_attempts=5
            ),
        )
