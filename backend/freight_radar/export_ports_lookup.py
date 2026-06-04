"""Export a compact port lookup so the browser can resolve a user's trade CSV.

The in-browser CSV upload (U1) recomputes exposure entirely client-side — nothing
leaves the browser. To resolve a user's ports (by UN/LOCODE, portid, or name) and
derive a shipping basin when no region column is given, the client needs the same
dim_port fields the Python resolver uses. We ship them once as a compact
columnar array (lazy-loaded only when the upload panel opens).

Format keeps it small (~2k ports):
  {"cols": ["portid","name","locode","continent","lat","lon"], "rows": [[...], ...]}
"""

from __future__ import annotations

import json
from pathlib import Path

import duckdb

from .config import db_path, publish_dir


def build_lookup(db=None, out=None) -> dict:
    db = Path(db) if db else db_path()
    out = Path(out) if out else publish_dir()
    con = duckdb.connect(str(db), read_only=True)
    try:
        rows = con.execute(
            "SELECT portid, portname, locode, continent, lat, lon FROM dim_port "
            "WHERE lat IS NOT NULL AND lon IS NOT NULL"
        ).fetchall()
    finally:
        con.close()
    payload = {
        "cols": ["portid", "name", "locode", "continent", "lat", "lon"],
        "rows": [[r[0], r[1], r[2] or "", r[3] or "",
                  round(float(r[4]), 4), round(float(r[5]), 4)] for r in rows],
    }
    path = out / "ports_lookup.json"
    path.write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "ports_lookup", "sidecar": "ports_lookup.json",
            "ports": len(payload["rows"]),
            "kb": round(path.stat().st_size / 1024, 1)}


def run(ctx) -> dict:
    return build_lookup(db=ctx.db_path, out=ctx.out_dir)


if __name__ == "__main__":
    print(json.dumps(build_lookup(), indent=2))
