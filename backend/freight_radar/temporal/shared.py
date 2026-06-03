"""Shared Temporal config + client helper."""

from __future__ import annotations

import os

from temporalio.client import Client

TASK_QUEUE = "freight-radar"
WORKFLOW_ID = "freight-radar-pipeline"
SCHEDULE_ID = "freight-radar-daily"


def temporal_address() -> str:
    return os.environ.get("TEMPORAL_ADDRESS", "localhost:7233")


def temporal_namespace() -> str:
    return os.environ.get("TEMPORAL_NAMESPACE", "default")


async def connect() -> Client:
    return await Client.connect(temporal_address(), namespace=temporal_namespace())
