"""Upstream-drift detector — declarative data contracts for the published sidecars.

The store is only as honest as its feeds. Each public source can change its schema,
go empty, or disappear without warning; when that happens we want to KNOW, not to ship
a quietly-degraded globe. This module declares, per sidecar, the shape the frontend +
agent actually depend on — required top-level keys, the items array and the keys each
item must carry, and a floor on how many items count as "alive" — and checks a data
directory against them.

Two lanes, mirroring the test strategy:

  * **non-live (CI gate):** ``tests/test_contracts.py`` validates the *committed* sidecars
    in ``frontend/public/data`` against these contracts, so a producer whose output drifts
    in a PR fails review.
  * **live (scheduled):** ``python -m freight_radar.contracts`` runs in ``refresh.yml`` over
    the *freshly fetched* data; an upstream schema change or an emptied feed fails the
    Action — the "scheduled contract-check that pings the maintainer" from the plan.

A contract is the floor, never a forecast: it asserts *shape + liveness*, never that a
value is correct. Episodic feeds (storms, hazards, flags) may legitimately be empty, so
their floor is 0 — drift there means a missing key or a broken array, not a quiet day.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .config import publish_dir


@dataclass(frozen=True)
class Contract:
    """The shape a sidecar must keep. `requires` are mandatory top-level keys; `items_key`
    names the array the UI iterates (None for a scalar sidecar); `item_requires` are keys
    every item must carry; `min_items` is the liveness floor; `is_array` marks a top-level
    JSON array (lanes/flags); `nonempty_lists` are top-level keys that must be non-empty
    arrays (the spine inside snapshot)."""

    requires: frozenset[str] = frozenset()
    items_key: str | None = None
    item_requires: frozenset[str] = frozenset()
    min_items: int = 0
    is_array: bool = False
    nonempty_lists: frozenset[str] = field(default_factory=frozenset)


# Keyed by sidecar stem (file is `<stem>.json`). Only the layers with a stable, well-known
# schema are contracted; uncontracted sidecars are simply not yet covered (reported by the
# CLI so the gap is visible, never silent). The geo/identity keys below are exactly what
# Globe.tsx + the tooltips read, so a drop here is a real, user-visible break.
SIDECAR_CONTRACTS: dict[str, Contract] = {
    # --- the measured spine (core) ---
    "snapshot": Contract(
        requires=frozenset({"generated_at", "as_of", "chokepoints", "ports", "source"}),
        nonempty_lists=frozenset({"chokepoints", "ports"}),
    ),
    "lanes": Contract(
        is_array=True,
        item_requires=frozenset({"from", "to", "intensity"}),
        min_items=1,
    ),
    "flags": Contract(
        is_array=True,
        item_requires=frozenset({"flag_id", "portid", "entity", "severity"}),
        min_items=0,  # a calm day can carry zero flags
    ),
    # --- cited context ring (the globe dot layers) ---
    "quakes": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"id", "mag", "lat", "lon", "place", "url"}),
        min_items=1,
    ),
    "news_geo": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"category", "lat", "lon", "url"}),
        min_items=1,
    ),
    "eonet": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"id", "title", "category", "lat", "lon", "url"}),
        min_items=1,
    ),
    "marine": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"name", "lat", "lon", "wave_height_m", "observed_at"}),
        min_items=1,
    ),
    "tides": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"port", "lat", "lon", "water_level_ft", "observed_at", "url"}),
        min_items=1,
    ),
    "streamflow": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"site", "river", "lat", "lon", "stage_ft", "url"}),
        min_items=1,
    ),
    "disruptions": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "events"}),
        items_key="events",
        item_requires=frozenset({"eventid", "type", "alertlevel", "lat", "lon", "name"}),
        min_items=0,  # GDACS can be quiet over the trailing window
    ),
    "gatun": Contract(
        requires=frozenset(
            {"generated_at", "as_of", "available", "current_level_ft", "lat", "lon", "projection"}
        ),
    ),
}

# how many items to spot-check for missing keys (catches partial drift without scanning all)
_ITEM_SAMPLE = 12


def check_payload(stem: str, payload: object) -> list[str]:
    """Validate one already-parsed sidecar payload against its contract. Returns a list of
    human-readable violation strings (empty == conforms). Unknown stems return []."""
    c = SIDECAR_CONTRACTS.get(stem)
    if c is None:
        return []
    v: list[str] = []

    if c.is_array:
        if not isinstance(payload, list):
            return [f"{stem}: expected a top-level JSON array, got {type(payload).__name__}"]
        items: list = payload
    else:
        if not isinstance(payload, dict):
            return [f"{stem}: expected a JSON object, got {type(payload).__name__}"]
        for k in sorted(c.requires):
            if k not in payload:
                v.append(f"{stem}: missing top-level key '{k}'")
        for k in sorted(c.nonempty_lists):
            val = payload.get(k)
            if not isinstance(val, list) or not val:
                v.append(f"{stem}: top-level '{k}' must be a non-empty array")
        if c.items_key is None:
            return v
        items = payload.get(c.items_key)  # type: ignore[assignment]
        if not isinstance(items, list):
            v.append(f"{stem}: items key '{c.items_key}' is missing or not an array")
            return v

    if len(items) < c.min_items:
        v.append(f"{stem}: only {len(items)} item(s), expected >= {c.min_items} (feed may be empty)")
    if c.item_requires:
        missing: set[str] = set()
        for it in items[:_ITEM_SAMPLE]:
            if isinstance(it, dict):
                missing |= {k for k in c.item_requires if k not in it}
        for k in sorted(missing):
            v.append(f"{stem}: item(s) missing key '{k}'")
    return v


def check_file(path: Path) -> list[str]:
    """Validate a sidecar file by its stem. A contracted-but-unparseable file is itself a
    violation."""
    stem = path.stem
    if stem not in SIDECAR_CONTRACTS:
        return []
    try:
        payload = json.loads(path.read_text())
    except (OSError, ValueError) as e:
        return [f"{stem}: could not read/parse ({e})"]
    return check_payload(stem, payload)


def check_dir(data_dir: Path) -> tuple[dict[str, list[str]], list[str]]:
    """Validate every contracted sidecar in `data_dir`. Returns (violations_by_stem, missing)
    where `missing` lists contracted sidecars that are absent (a degraded-to-absent feed)."""
    violations: dict[str, list[str]] = {}
    missing: list[str] = []
    for stem in sorted(SIDECAR_CONTRACTS):
        p = data_dir / f"{stem}.json"
        if not p.exists():
            missing.append(stem)
            continue
        v = check_file(p)
        if v:
            violations[stem] = v
    return violations, missing


def main(argv: list[str] | None = None) -> int:
    """CLI: validate a data dir, print a report, exit 1 on any schema/liveness drift. Missing
    sidecars are reported as warnings (a feed can transiently degrade-to-absent) but do not
    fail on their own — a *contracted, present, malformed* feed is the hard failure."""
    args = argv if argv is not None else sys.argv[1:]
    data_dir = Path(args[0]) if args else publish_dir()
    violations, missing = check_dir(data_dir)

    n_checked = len(SIDECAR_CONTRACTS) - len(missing)
    print(f"contract check: {n_checked}/{len(SIDECAR_CONTRACTS)} contracted sidecars present in {data_dir}")
    if missing:
        print(f"  ⚠ absent (degraded-to-absent, not failing): {', '.join(missing)}")
    if not violations:
        print("  ✓ no schema/liveness drift")
        return 0
    print(f"  ✗ DRIFT in {len(violations)} sidecar(s):")
    for stem in sorted(violations):
        for msg in violations[stem]:
            print(f"      {msg}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
