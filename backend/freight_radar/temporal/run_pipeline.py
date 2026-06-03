"""Run the pipeline once against a running Temporal server (outside the Schedule).

    python -m freight_radar.temporal.run_pipeline                # full run (fetches)
    python -m freight_radar.temporal.run_pipeline --skip-fetch   # use existing DuckDB
"""

from __future__ import annotations

import argparse
import asyncio
import json

from .shared import TASK_QUEUE, WORKFLOW_ID, connect
from .workflow import FreightRadarWorkflow


async def run_once(skip_fetch: bool = False) -> dict:
    client = await connect()
    return await client.execute_workflow(
        FreightRadarWorkflow.run,
        {"skip_fetch": skip_fetch},
        id=f"{WORKFLOW_ID}-manual",
        task_queue=TASK_QUEUE,
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-fetch", action="store_true")
    args = ap.parse_args()
    result = asyncio.run(run_once(skip_fetch=args.skip_fetch))
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
