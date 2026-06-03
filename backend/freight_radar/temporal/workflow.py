"""FreightRadarWorkflow — the durable fetch->detect->attribute->assemble->publish loop.

A Temporal Schedule (schedule.py) triggers one execution per tick. Each execution
is crash-durable: if the worker dies mid-run, Temporal replays workflow state and
re-drives from the last *incomplete* activity on restart — the activities that
already finished are not re-run. That durability is the interview-gold property;
the kill-worker-mid-run -> restart -> resume demo is exactly this.
"""

from __future__ import annotations

from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from . import activities


@workflow.defn
class FreightRadarWorkflow:
    def __init__(self) -> None:
        self._stage = "init"
        self._summary: dict = {}
        self._refresh = False

    @workflow.run
    async def run(self, params: dict | None = None) -> dict:
        params = params or {}
        retry = RetryPolicy(
            initial_interval=timedelta(seconds=2),
            backoff_coefficient=2.0,
            maximum_interval=timedelta(seconds=30),
            maximum_attempts=3,
        )

        async def step(name, fn, *args, timeout_s=180):
            self._stage = name
            return await workflow.execute_activity(
                fn, *args, start_to_close_timeout=timedelta(seconds=timeout_s), retry_policy=retry
            )

        result: dict = {}
        if not params.get("skip_fetch"):
            result["fetch"] = await step("fetch", activities.fetch_portwatch, timeout_s=300)

        detect = await step("detect", activities.compute_and_detect)
        result["detect"] = detect
        result["attribute"] = await step("attribute", activities.llm_attribute, detect["flag_ids"])
        result["assemble"] = await step("assemble", activities.assemble_snapshot)
        result["publish"] = await step("publish", activities.publish)

        self._stage = "done"
        self._summary = result
        return result

    @workflow.query
    def status(self) -> dict:
        return {"stage": self._stage, "summary": self._summary}

    @workflow.signal
    def refresh(self) -> None:
        # Hook for an on-demand re-run trigger (the Schedule is the steady loop).
        self._refresh = True
