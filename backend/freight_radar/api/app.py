"""Read-only FastAPI surface over the published snapshot (the docker/live path).

The static frontend can read the JSON files directly; this API serves the same
data dynamically (with ETags) plus a /health that reports data freshness so the
UI can show 'data as of <date>' and a source-status badge honestly.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import duckdb
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from ..config import db_path, publish_dir

app = FastAPI(title="Freight Radar API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET"],
    allow_headers=["*"],
)


def _serve(filename: str, response: Response) -> dict | list:
    path = publish_dir() / filename
    if not path.exists():
        response.status_code = 503
        return {"error": f"{filename} not published yet"}
    raw = path.read_bytes()
    response.headers["ETag"] = hashlib.sha1(raw).hexdigest()[:16]
    response.headers["Cache-Control"] = "no-cache"
    return json.loads(raw)


@app.get("/api/health")
def health() -> dict:
    out: dict = {"status": "ok"}
    manifest = publish_dir() / "manifest.json"
    if manifest.exists():
        out["manifest"] = json.loads(manifest.read_text())
    else:
        out["status"] = "no_data"
    # best-effort source freshness from the DuckDB metadata
    try:
        con = duckdb.connect(str(db_path()), read_only=True)
        row = con.execute(
            "SELECT source, status, max_data_date, last_success FROM meta_source_status"
        ).fetchall()
        con.close()
        out["sources"] = [
            {"source": r[0], "status": r[1], "max_data_date": str(r[2]), "last_success": str(r[3])}
            for r in row
        ]
    except (duckdb.Error, FileNotFoundError):
        out["sources"] = []
    return out


@app.get("/api/manifest")
def manifest(response: Response):
    return _serve("manifest.json", response)


@app.get("/api/snapshot")
def snapshot(response: Response):
    return _serve("snapshot.json", response)


@app.get("/api/flags")
def flags(response: Response):
    return _serve("flags.json", response)


@app.get("/api/lanes")
def lanes(response: Response):
    return _serve("lanes.json", response)
