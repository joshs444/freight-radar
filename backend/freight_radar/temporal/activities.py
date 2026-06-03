"""The 5 pipeline activities: fetch -> detect -> attribute -> assemble -> publish.

Each wraps already-proven backend code. Activities do the real I/O (network,
DuckDB, files); the workflow (workflow.py) just orchestrates them durably.

The attribution activity is the dedup ledger: it 'attributes' (and would call an
LLM for) ONLY flags not seen before this ISO week. A second identical run sees
every flag_id already in the ledger and makes ZERO calls — proven in tests.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import duckdb
from temporalio import activity

from ..config import INCREMENTAL_REPULL_DAYS, db_path, publish_dir
from ..detect import run_detection
from ..export_snapshot import export
from ..ingest.dims import load_dims
from ..ingest.portwatch import load_chokepoint_daily, load_port_daily
from ..publish import write_manifest
from ..storage.db import connect as db_connect, join_coverage

_LEDGER_SQL = """
CREATE TABLE IF NOT EXISTS meta_attribution (
    flag_id       VARCHAR PRIMARY KEY,
    attributed_at TIMESTAMP,
    brief_final   VARCHAR
);
"""


# --- 1. fetch --------------------------------------------------------------
@activity.defn
async def fetch_portwatch(days: int = INCREMENTAL_REPULL_DAYS) -> dict:
    """Trailing re-pull of the PortWatch backbone (values are revisable)."""
    from ..arcgis import ArcGISClient

    con = db_connect(db_path())
    end = date.today()
    start = end - timedelta(days=days)
    async with ArcGISClient() as client:
        dims = await load_dims(con, client)
        choke = await load_chokepoint_daily(con, client, start, end)
        ports = await load_port_daily(con, client, start, end)
    cov = join_coverage(con, "fct_port_daily", "dim_port")
    con.close()
    activity.logger.info("fetch: choke=%s ports=%s cov=%.3f", choke, ports, cov)
    return {"dims": dims, "chokepoint_rows": choke, "port_rows": ports, "port_join_coverage": round(cov, 4)}


# --- 2. compute + detect ---------------------------------------------------
@activity.defn
async def compute_and_detect() -> dict:
    flags = run_detection.run(db_path(), flags_json=publish_dir() / "flags.json")
    by_kind: dict[str, int] = {}
    for f in flags:
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
    return {
        "n_flags": len(flags),
        "by_kind": by_kind,
        "flag_ids": [f.flag_id for f in flags],
    }


# --- 3. llm attribute (dedup ledger) ---------------------------------------
class _Attributor:
    """Template-first attributor (zero marginal cost). Counts a 'call' per NEW
    flag; an Ollama/LLM polish would slot in here, fired only on these."""

    def __init__(self) -> None:
        self.calls = 0

    def attribute(self, brief_md: str) -> str:
        self.calls += 1
        # The brief already carries the real, Python-computed numbers. A local
        # LLM could polish prose here; default is the template (no external call).
        return brief_md


@activity.defn
async def llm_attribute(flag_ids: list[str]) -> dict:
    con = duckdb.connect(str(db_path()))
    try:
        con.execute(_LEDGER_SQL)
        seen = {r[0] for r in con.execute("SELECT flag_id FROM meta_attribution").fetchall()}
        fresh = [fid for fid in flag_ids if fid not in seen]
        att = _Attributor()
        now = datetime.now()
        for fid in fresh:
            row = con.execute(
                "SELECT brief_md FROM fct_flags WHERE flag_id = ?", [fid]
            ).fetchone()
            brief = att.attribute(row[0] if row else "")
            con.execute(
                "INSERT OR REPLACE INTO meta_attribution VALUES (?, ?, ?)",
                [fid, now, brief],
            )
    finally:
        con.close()
    activity.logger.info("attribute: %s new of %s flags", len(fresh), len(flag_ids))
    return {"total_flags": len(flag_ids), "new_attributions": len(fresh), "llm_calls": att.calls}


# --- 4. assemble snapshot --------------------------------------------------
@activity.defn
async def assemble_snapshot() -> dict:
    # real detection (compute_and_detect) owns flags.json; don't clobber it.
    return export(db_path=db_path(), out_dir=publish_dir(), write_flags=False)


# --- 5. publish (atomic manifest + version bump) ---------------------------
@activity.defn
async def publish() -> dict:
    manifest = write_manifest(publish_dir())
    activity.logger.info(
        "publish: v%s as_of=%s flags=%s",
        manifest["version"], manifest["as_of"], manifest["flag_count"],
    )
    return manifest


ALL_ACTIVITIES = [
    fetch_portwatch,
    compute_and_detect,
    llm_attribute,
    assemble_snapshot,
    publish,
]
