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
    }
    fd, tmp = tempfile.mkstemp(dir=out_dir, suffix=".tmp")
    with os.fdopen(fd, "w") as fh:
        json.dump(manifest, fh, indent=2)
    os.replace(tmp, manifest_path)
    os.chmod(manifest_path, 0o644)  # mkstemp is 0600; this file is served statically
    return manifest


def publish_static(db=None, out_dir=None) -> dict:
    """Detect -> snapshot/lanes -> manifest, no Temporal. Returns the manifest."""
    from .detect import run_detection

    out = Path(out_dir) if out_dir else publish_dir()
    db = Path(db) if db else db_path()
    run_detection.run(db, flags_json=out / "flags.json")
    export(db_path=db, out_dir=out, write_flags=False)
    return write_manifest(out)


if __name__ == "__main__":
    m = publish_static()
    print("=== published (static) ===")
    print(json.dumps(m, indent=2))
