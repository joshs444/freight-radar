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
from datetime import datetime
from pathlib import Path

from .config import db_path, publish_dir
from .export_snapshot import LANES, SOURCE, export


# Optional signal sidecars; the manifest reports which are present + fresh so the
# UI and /api/health can show freshness per layer (honest "what's loaded").
_SIDECARS = ("exposure", "news", "timeseries", "ports_lookup", "ships", "market", "stress",
             "world", "events", "brief", "disruptions", "gatun", "weather", "wind", "dwell")


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


def write_manifest(out_dir: Path) -> dict:
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
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "source": SOURCE,
        "flag_count": len(flags),
        "chokepoints": len(snap.get("chokepoints", [])),
        "ports": len(snap.get("ports", [])),
        "lanes": len(LANES),
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
    run_detection.run(db, flags_json=out / "flags.json")
    run_enrichers(build_ctx(db=db, out=out))  # exposure + news + timeseries (+ future layers)
    export(db_path=db, out_dir=out, write_flags=False)
    return write_manifest(out)


if __name__ == "__main__":
    m = publish_static()
    print("=== published (static) ===")
    print(json.dumps(m, indent=2))
