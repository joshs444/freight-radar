"""Publish helpers shared by the Temporal pipeline and the static publisher.

``write_manifest`` stamps an atomic, version-bumped manifest.json next to the
published snapshot/flags so the frontend (and /api/health) can show freshness.

``publish_static`` runs the whole publish WITHOUT Temporal (detect -> snapshot ->
manifest) — used for the free static-deploy path and CI, and to regenerate the
committed JSON. The Temporal workflow is the always-on version of the same steps.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .config import db_path, publish_dir
from .export_snapshot import LANES, SOURCE, export
from .registry.layers import SIDECARS as _SIDECARS  # the optional-sidecar freshness set

# `_SIDECARS` is now DERIVED from the registry (registry/layers.py): every layer with
# `manifest_sidecar=True`. This killed the hand-maintained tuple — and with it the
# `dwell` orphan it used to list (nothing produces dwell.json), the registry's first
# reconciliation. The manifest reports which sidecars are present + fresh so the UI and
# /api/health can show freshness per layer (honest "what's loaded").


def read_lineage(db: Path) -> dict:
    """Latest Write-Audit-Publish verdict per fact table, from meta_publish_runs.

    Reads the most recent promotion for each staged table so the manifest can show
    the DQ verdict + deterministic lineage_run_id that cleared the live facts. Best
    effort: a missing DB/table (fresh checkout, manifest-only republish) yields an
    empty dict rather than failing the publish.
    """
    db = Path(db)
    if not db.exists():
        return {}
    import duckdb

    try:
        con = duckdb.connect(str(db), read_only=True)
    except duckdb.Error:
        return {}
    try:
        rows = con.execute(
            "SELECT lineage_run_id, verdict, rows_promoted, checks_run "
            "FROM meta_publish_runs QUALIFY row_number() OVER "
            "(PARTITION BY split_part(lineage_run_id, '-', 1) ORDER BY promoted_at DESC) = 1 "
            "ORDER BY lineage_run_id"
        ).fetchall()
    except duckdb.Error:
        return {}
    finally:
        con.close()
    if not rows:
        return {}
    runs = [
        {"lineage_run_id": r[0], "verdict": r[1], "rows_promoted": int(r[2]), "checks_run": int(r[3])}
        for r in rows
    ]
    return {"verdict": "pass" if all(r["verdict"] == "pass" for r in runs) else "fail", "runs": runs}


def _layers(out_dir: Path) -> dict:
    out: dict[str, dict] = {}
    for name in _SIDECARS:
        p = out_dir / f"{name}.json"
        if not p.exists():
            out[name] = {"present": False}
            continue
        info = {"present": True, "kb": round(p.stat().st_size / 1024, 1)}
        try:
            data = json.loads(p.read_text())
            if isinstance(data, dict) and data.get("generated_at"):
                info["generated_at"] = data["generated_at"]
        except (json.JSONDecodeError, OSError):
            pass
        out[name] = info
    return out


def write_manifest(out_dir: Path, lineage: dict | None = None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    snap = json.loads((out_dir / "snapshot.json").read_text())
    flags = json.loads((out_dir / "flags.json").read_text())

    manifest_path = out_dir / "manifest.json"
    prev = 0
    if manifest_path.exists():
        try:
            prev = int(json.loads(manifest_path.read_text()).get("version", 0))
        except (ValueError, json.JSONDecodeError):
            prev = 0

    manifest = {
        "version": prev + 1,
        "as_of": snap.get("as_of"),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SOURCE,
        "flag_count": len(flags),
        "chokepoints": len(snap.get("chokepoints", [])),
        "ports": len(snap.get("ports", [])),
        "lanes": len(LANES),
        # Write-Audit-Publish lineage: the DQ verdict + the deterministic run id(s)
        # that cleared this publish, so each map is traceable to the audit that
        # produced it. Passed in by the caller (deterministic; never random/now).
        "lineage": lineage or read_lineage(db_path()),
        "layers": _layers(out_dir),
    }
    fd, tmp = tempfile.mkstemp(dir=out_dir, suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(manifest, fh, indent=2)
    os.replace(tmp, manifest_path)
    os.chmod(manifest_path, 0o644)  # mkstemp is 0600; this file is served statically
    return manifest


def publish_static(db=None, out_dir=None) -> dict:
    """Detect -> run ALL enrichers (registry) -> snapshot/lanes -> manifest, no Temporal."""
    from .detect import run_detection
    from .enrich import build_ctx, run_enrichers

    out = Path(out_dir) if out_dir else publish_dir()
    db = Path(db) if db else db_path()
    from .honesty.scorecard import write as write_scorecard

    run_detection.run(db, flags_json=out / "flags.json")
    run_enrichers(build_ctx(db=db, out=out))  # exposure + news + timeseries (+ future layers)
    export(db_path=db, out_dir=out, write_flags=False)
    write_scorecard(out)  # the honesty scorecard (Harness Layer 4) — registry-derived, free
    return write_manifest(out)


if __name__ == "__main__":
    from ._log import configure as configure_logging

    configure_logging()
    m = publish_static()
    print("=== published (static) ===")
    print(json.dumps(m, indent=2))
