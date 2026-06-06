"""The enricher runner — thin now that the registry owns the layer list.

``run_enrichers`` runs every enricher the registry declares (in pipeline order),
writes its one sidecar, and SWALLOWS per-enricher failures (the server-side mirror
of the frontend's ``.catch(()=>null)``) — one bad layer never aborts publish. Both
``publish_static`` and the Temporal loop call it.

The layer list, the (name, run, depends_on_flags) tuples, and the adapters all live
in :mod:`freight_radar.registry.layers` now — adding a layer is one append there, not
an edit here. ``EnrichCtx`` and ``ENRICHERS`` are re-exported so existing imports
(`from freight_radar.enrich import EnrichCtx, ENRICHERS, run_enrichers, build_ctx`)
keep working unchanged.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import duckdb

from .config import db_path, publish_dir
from .registry.layers import ENRICHERS, EnrichCtx  # noqa: F401 — re-exported for callers

log = logging.getLogger(__name__)


def run_enrichers(ctx: EnrichCtx) -> dict:
    """Run every registered enricher; swallow per-enricher failures."""
    receipts: dict[str, dict] = {}
    for name, run, _ in ENRICHERS:
        try:
            receipts[name] = run(ctx)
        except Exception as e:  # noqa: BLE001 — degrade, never abort publish
            receipts[name] = {"name": name, "error": repr(e)}
            log.warning("enricher %s failed: %r", name, e)
    return receipts


def build_ctx(db=None, out=None) -> EnrichCtx:
    """Build an EnrichCtx from the configured DB + publish dir (as_of from DuckDB)."""
    db = Path(db) if db else db_path()
    out = Path(out) if out else publish_dir()
    con = duckdb.connect(str(db), read_only=True)
    try:
        row = con.execute("SELECT max(date) FROM fct_chokepoint_daily").fetchone()
        as_of = str(row[0]) if row and row[0] is not None else ""
    finally:
        con.close()
    return EnrichCtx(
        db_path=db,
        out_dir=out,
        flags_path=out / "flags.json",
        as_of=as_of,
        today=date.today().isoformat(),
    )
