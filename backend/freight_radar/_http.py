"""Shared HTTP resilience for the weekly live fetchers (weather, hazards, gatun,
market, news).

One place for the timeout + browser User-Agent + a retry that fires ONLY on transient
transport errors (connect/read timeouts, dropped connections) — never on a 4xx/5xx,
which usually means "not available right now" and is handled by each caller's degrade
path. Mirrors the GFS fetch policy in wind.py so every live layer behaves the same: a
blip is retried, a real absence degrades cleanly to an empty layer.
"""

from __future__ import annotations

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

# A realistic UA — some of these public endpoints 403 the default httpx UA.
BROWSER_UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"
DEFAULT_TIMEOUT = 20.0


def client(timeout: float = DEFAULT_TIMEOUT, **kwargs) -> httpx.Client:
    """An httpx.Client with the shared timeout, UA, and redirect-following."""
    headers = {"User-Agent": BROWSER_UA, **kwargs.pop("headers", {})}
    return httpx.Client(timeout=timeout, headers=headers, follow_redirects=True, **kwargs)


@retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, max=8),
    retry=retry_if_exception_type(httpx.TransportError),
)
def get(c: httpx.Client, url: str, **kwargs) -> httpx.Response:
    """GET with a transport-only retry (transient blips), letting status errors through
    so the caller's own except path decides whether a non-200 means "degrade"."""
    return c.get(url, **kwargs)
