"""Idempotent Schedule management — the steady 'always-on' loop.

    python -m freight_radar.temporal.schedule           # ensure (create or update)
    python -m freight_radar.temporal.schedule --trigger # run one tick now

PortWatch refreshes weekly, so a frequent schedule mostly re-pulls revisable
values + re-detects; the interval is config-driven (SCHEDULE_INTERVAL_HOURS).
"""

from __future__ import annotations

import argparse
import asyncio
import os
from datetime import timedelta

from temporalio.client import (
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleIntervalSpec,
    ScheduleSpec,
    ScheduleState,
)
from temporalio.service import RPCError

from .shared import SCHEDULE_ID, TASK_QUEUE, WORKFLOW_ID, connect
from .workflow import FreightRadarWorkflow


def _interval() -> timedelta:
    return timedelta(hours=float(os.environ.get("SCHEDULE_INTERVAL_HOURS", "6")))


def _schedule() -> Schedule:
    return Schedule(
        action=ScheduleActionStartWorkflow(
            FreightRadarWorkflow.run,
            {},
            id=WORKFLOW_ID,
            task_queue=TASK_QUEUE,
        ),
        spec=ScheduleSpec(intervals=[ScheduleIntervalSpec(every=_interval())]),
        state=ScheduleState(note="Freight Radar fetch->detect->attribute->publish"),
    )


async def ensure_schedule() -> str:
    """Create the schedule, or update it if it already exists. Idempotent."""
    client = await connect()
    try:
        await client.create_schedule(SCHEDULE_ID, _schedule())
        return "created"
    except RPCError:
        handle = client.get_schedule_handle(SCHEDULE_ID)
        await handle.update(lambda _input: _schedule())
        return "updated"


async def trigger_now() -> None:
    client = await connect()
    await client.get_schedule_handle(SCHEDULE_ID).trigger()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trigger", action="store_true", help="run one tick immediately")
    args = ap.parse_args()
    if args.trigger:
        asyncio.run(trigger_now())
        print(f"triggered schedule {SCHEDULE_ID}")
    else:
        result = asyncio.run(ensure_schedule())
        print(f"schedule {SCHEDULE_ID}: {result} (every {_interval()})")


if __name__ == "__main__":
    main()
