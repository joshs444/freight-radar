"""Golden-master harness — Layer 2 of the Acceptance Harness (the oracle).

Runs the deterministic, OFFLINE publish pipeline against the hermetic dbt fixture
DB and snapshots the SPINE/SIGNAL sidecars, with the two volatile fields
(``generated_at``, ``lineage_run_id``) normalized out. The committed snapshots in
``tests/golden/`` are the frozen expected output; ``test_golden_sidecars.py``
asserts the live run reproduces them byte-for-byte.

This is the safety net that makes "pure refactor" *provable*: any change to a
computed number shows up as an unblessed diff (red), never slips through. The P0
registry refactor must leave every one of these byte-identical.

Network is hard-blocked — every network layer routes through ``freight_radar._http``,
so blocking ``_http.client``/``_http.get`` makes the run mirror CI exactly (no
network): the network CONTEXT layers (news_geo, quakes, market, weather,
disruptions) degrade to absent, and only the deterministic, DB-derived layers are
captured. Re-bless a *deliberate* change explicitly (an agent can't silently "fix"
a failing golden by editing it — the bless is a reviewable commit)::

    cd backend && uv run python -m tests.golden_harness bless
"""

from __future__ import annotations

import importlib.util
import os
import re
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]  # backend/tests/ -> repo root
FIXTURE_DB_BUILDER = REPO_ROOT / "dbt" / "ci" / "build_fixture_db.py"
GOLDEN_DIR = Path(__file__).resolve().parent / "golden"

# The deterministic, offline-reproducible sidecars (pure functions of the fixture
# DB). The network CONTEXT layers (news_geo / quakes / market / weather /
# disruptions) are intentionally excluded: they pull live data and degrade to
# absent offline, so they can't be a frozen master. Their parser correctness is
# covered by the per-layer tests (test_news_geo, test_quakes, ...).
GOLDEN_SIDECARS = (
    "snapshot",
    "lanes",
    "flags",
    "timeseries",
    "stress",
    "world",
    "events",
    "exposure",
    "gatun",
    "ports_lookup",
    "brief",
)

# The only fields that legitimately vary run-to-run. Everything else is a pure
# function of the fixture inputs, so it must be byte-stable.
_VOLATILE = (
    re.compile(r'("generated_at"\s*:\s*)"[^"]*"'),
    re.compile(r'("lineage_run_id"\s*:\s*)"[^"]*"'),
)


def normalize(text: str) -> str:
    """Strip the two volatile fields so the diff is over semantics, not clocks."""
    for rx in _VOLATILE:
        text = rx.sub(r'\1"<NORM>"', text)
    return text


def _build_fixture_db(db_path: Path) -> None:
    """Build the hermetic CI warehouse from committed CSVs with the exact prod DDL."""
    spec = importlib.util.spec_from_file_location("_fr_fixture_builder", FIXTURE_DB_BUILDER)
    assert spec and spec.loader, f"cannot load fixture builder at {FIXTURE_DB_BUILDER}"
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    os.environ["FREIGHT_RADAR_DB"] = str(db_path)
    mod.main()


def _seed_prior_ledger(db_path: Path, state: Path) -> None:
    """Seed the tmp flags ledger from the fixture's committed prior-flag rows
    (``fct_flags.csv`` — the fixture's "last week's run").

    The committed ledger is the ONLY prior-flags source for lifecycle
    (ADR-0009), so without this seed the goldens would stop exercising
    ``ongoing`` continuity and the resolved tombstones the fixture's prior rows
    deliberately produce.
    """
    import duckdb
    import pandas as pd

    from freight_radar import ledger

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        rows = con.execute(
            "SELECT * FROM fct_flags "
            "WHERE detected_date = (SELECT max(detected_date) FROM fct_flags) "
            "  AND COALESCE(lifecycle, '') <> 'resolved'"
        ).df()
    finally:
        con.close()
    if rows.empty:
        return
    flags = []
    for _, r in rows.iterrows():
        d = {}
        for k in ledger.FLAG_FIELDS:
            v = r[k] if k in r else None
            if v is not None and pd.isna(v):
                v = None
            elif hasattr(v, "item"):  # numpy scalar -> plain Python for JSON
                v = v.item()
            d[k] = str(v)[:10] if k == "as_of" else v
        flags.append(d)
    ledger.append_flags(str(rows["as_of"].max())[:10], flags, state)


def capture() -> dict[str, str]:
    """Build the fixture DB, run the offline pipeline, return {name: normalized json}."""
    from freight_radar import _http
    from freight_radar.publish import publish_static

    def _blocked(*_a, **_k):
        raise RuntimeError("network blocked (golden-master harness runs offline)")

    orig_client, orig_get = _http.client, _http.get
    with tempfile.TemporaryDirectory() as tmp:
        tmpd = Path(tmp)
        db = tmpd / "fixture.duckdb"
        out = tmpd / "out"
        out.mkdir()
        _build_fixture_db(db)
        # Isolate the committed-state ledgers (ADR-0009) exactly like the DB: the
        # detector seeds lifecycle from data/state/flags_ledger.jsonl, so a capture
        # against the REAL ledger would drift with production history instead of
        # being a pure function of the fixture inputs. The fixture's prior rows
        # are seeded into the tmp ledger so lifecycle continuity stays covered.
        os.environ["FREIGHT_RADAR_STATE_DIR"] = str(tmpd / "state")
        _seed_prior_ledger(db, tmpd / "state")
        _http.client = _blocked  # type: ignore[assignment]
        _http.get = _blocked  # type: ignore[assignment]
        try:
            publish_static(db=str(db), out_dir=str(out))
        finally:
            _http.client = orig_client  # restore — never leak the block to other tests
            _http.get = orig_get
        result: dict[str, str] = {}
        for name in GOLDEN_SIDECARS:
            p = out / f"{name}.json"
            if not p.exists():
                raise AssertionError(
                    f"expected deterministic sidecar missing offline: {name}.json"
                )
            result[name] = normalize(p.read_text())
        return result


def bless() -> None:
    """Regenerate the committed golden masters (a reviewable, intentional act)."""
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    snaps = capture()
    for name, text in snaps.items():
        (GOLDEN_DIR / f"{name}.json").write_text(text)
        print(f"  blessed golden/{name}.json ({len(text):,} bytes)")
    print(f"re-blessed {len(snaps)} golden sidecars -> {GOLDEN_DIR}")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "bless":
        bless()
    else:
        print("usage: python -m tests.golden_harness bless", file=sys.stderr)
        sys.exit(2)
