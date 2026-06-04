"""Async ArcGIS Feature Service client with correct offset pagination.

The PortWatch layers cap every response at 1000 rows and set
``exceededTransferLimit: true`` when more remain. We page with ``resultOffset``
ordered by a stable unique field (``ObjectId``) so paging is deterministic, and
chunk long date windows so several pages fetch concurrently (bounded).
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .config import ARCGIS_HOST, DEFAULT_CONCURRENCY, PAGE_SIZE


class ArcGISError(RuntimeError):
    """An esri error envelope, empty body, or otherwise unusable response."""


def _assert_fetch_complete(n_rows: int, server_count: int, service: str, where: str) -> None:
    """Raise if we paged fewer rows than the server says exist for ``where``.

    A silently dropped page (network hiccup mid-pagination, an off-by-one offset)
    would otherwise shrink the window with no error. ``returnCountOnly`` gives the
    authoritative total; fewer rows than that is a hard, retryable failure. We only
    guard the under-count direction — deterministic ObjectId paging never duplicates,
    and a couple extra rows from a concurrent upstream insert is not a data loss.
    """
    if n_rows < server_count:
        raise ArcGISError(
            f"incomplete fetch from {service}: paged {n_rows} rows but server "
            f"reports {server_count} for [{where}] — a page was dropped"
        )


def _date_chunks(start: date, end: date, chunk_days: int) -> list[tuple[date, date]]:
    """Split [start, end] inclusive into <=chunk_days windows."""
    chunks: list[tuple[date, date]] = []
    cur = start
    while cur <= end:
        hi = min(cur + timedelta(days=chunk_days - 1), end)
        chunks.append((cur, hi))
        cur = hi + timedelta(days=1)
    return chunks


class ArcGISClient:
    def __init__(
        self,
        host: str = ARCGIS_HOST,
        page_size: int = PAGE_SIZE,
        concurrency: int = DEFAULT_CONCURRENCY,
        timeout: float = 45.0,
    ) -> None:
        self.host = host.rstrip("/")
        self.page_size = page_size
        self._sem = asyncio.Semaphore(concurrency)
        self._client = httpx.AsyncClient(
            timeout=timeout,
            headers={"User-Agent": "freight-radar/0.1 (+portfolio)"},
        )

    async def __aenter__(self) -> "ArcGISClient":
        return self

    async def __aexit__(self, *_exc) -> None:
        await self._client.aclose()

    def _url(self, service: str) -> str:
        return f"{self.host}/{service}/FeatureServer/0/query"

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=0.6, max=10),
        retry=retry_if_exception_type((httpx.HTTPError, ArcGISError)),
    )
    async def _fetch_page(self, service: str, params: dict) -> dict:
        async with self._sem:
            resp = await self._client.get(self._url(service), params=params)
        resp.raise_for_status()
        if not resp.text.strip():
            # The public service intermittently returns an empty body — retry.
            raise ArcGISError(f"empty response body from {service}")
        data = resp.json()
        if isinstance(data, dict) and "error" in data:
            raise ArcGISError(f"esri error from {service}: {data['error']}")
        return data

    async def count(self, service: str, where: str = "1=1") -> int:
        data = await self._fetch_page(
            service, {"where": where, "returnCountOnly": "true", "f": "json"}
        )
        return int(data.get("count", 0))

    async def query_all(
        self,
        service: str,
        where: str = "1=1",
        out_fields: str = "*",
        order_by: str = "ObjectId",
        return_geometry: bool = False,
    ) -> list[dict]:
        """Fetch every row matching ``where``, paging until the server is dry."""
        rows: list[dict] = []
        offset = 0
        while True:
            params = {
                "where": where,
                "outFields": out_fields,
                "f": "json",
                "resultOffset": offset,
                "resultRecordCount": self.page_size,
                "returnGeometry": "true" if return_geometry else "false",
            }
            if order_by:
                params["orderByFields"] = order_by
            data = await self._fetch_page(service, params)
            feats = data.get("features", [])
            rows.extend(f["attributes"] for f in feats)
            exceeded = bool(data.get("exceededTransferLimit", False))
            if not feats or (len(feats) < self.page_size and not exceeded):
                break
            offset += self.page_size
        return rows

    async def query_date_window(
        self,
        service: str,
        start: date,
        end: date,
        out_fields: str = "*",
        date_col: str = "date",
        chunk_days: int = 20,
        verify_count: bool = False,
    ) -> list[dict]:
        """Fetch a [start, end] date window, chunked so pages fetch concurrently.

        Each chunk pages sequentially; the shared semaphore bounds total in-flight
        requests, so wide port backfills stay fast without hammering the service.

        ``verify_count`` adds one ``returnCountOnly`` call over the whole window and
        asserts we paged at least that many rows — turning a silently dropped page
        into a hard (retryable) failure instead of a quietly short window.
        """
        chunks = _date_chunks(start, end, chunk_days)
        tasks = [
            self.query_all(
                service,
                where=f"{date_col}>=DATE '{a.isoformat()}' AND {date_col}<=DATE '{b.isoformat()}'",
                out_fields=out_fields,
                order_by="ObjectId",
            )
            for a, b in chunks
        ]
        results = await asyncio.gather(*tasks)
        rows = [row for chunk in results for row in chunk]
        if verify_count:
            window = (
                f"{date_col}>=DATE '{start.isoformat()}' "
                f"AND {date_col}<=DATE '{end.isoformat()}'"
            )
            _assert_fetch_complete(len(rows), await self.count(service, window), service, window)
        return rows
