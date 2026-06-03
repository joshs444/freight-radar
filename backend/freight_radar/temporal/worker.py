"""The Temporal worker: registers the workflow + activities and polls the queue.

    python -m freight_radar.temporal.worker
"""

from __future__ import annotations

import asyncio
import logging

from temporalio.worker import Worker

from .activities import ALL_ACTIVITIES
from .shared import TASK_QUEUE, connect
from .workflow import FreightRadarWorkflow


async def main() -> None:
    logging.basicConfig(level=logging.INFO)
    client = await connect()
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[FreightRadarWorkflow],
        activities=ALL_ACTIVITIES,
    )
    logging.info("Freight Radar worker polling task queue %r", TASK_QUEUE)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
