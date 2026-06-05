"""Package logging.

A library shouldn't configure the root logger, so the fetchers only ever call
`get_logger()` and emit records. The CLI entrypoints (backfill, publish, wind, the
AIS consumer) call `configure()` once so a degraded weekly layer leaves a visible
WARNING in the CI log instead of vanishing into a swallowed exception.
"""

from __future__ import annotations

import logging
import os

_CONFIGURED = False


def configure() -> None:
    """Idempotent logging setup for the CLI entrypoints. Level via FR_LOG_LEVEL."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    logging.basicConfig(
        level=os.environ.get("FR_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    # httpx logs every request at INFO — too chatty for the weekly fetchers; we only
    # care when one of our layers actually degrades (a WARNING from this package).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    _CONFIGURED = True


def get_logger(name: str = "freight_radar") -> logging.Logger:
    return logging.getLogger(name)
