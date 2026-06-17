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
from .registry.shapes import SHAPES, to_contract_kwargs


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


# Keyed by sidecar stem (file is `<stem>.json`). DERIVED from the shape registry
# (registry/shapes.py) — the contracts are no longer a hand-maintained mirror: each stem's
# Contract is reduced from its Shape's declared contract floor. Only the layers with a
# stable, well-known schema have a Shape; uncontracted sidecars are simply not yet covered
# (reported by the CLI so the gap is visible, never silent). The geo/identity keys the
# shapes declare are exactly what Globe.tsx + the tooltips read, so a drop is a real break.
# (A migration test — test_shapes_contracts.py — pins the derived dict to the old literals.)
SIDECAR_CONTRACTS: dict[str, Contract] = {
    stem: Contract(**to_contract_kwargs(stem)) for stem in SHAPES
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


# The measured spine the app blocks on — absent is fatal, so a broken one HARD-fails the
# publish (an absent spine beats a silently-broken one). Everything else degrades to dark.
# stress + timeseries join the spine (H1-F): the headline/Board read stress, and the
# play-through-history view blocks on timeseries — a broken one must fail, not ship dark.
CORE_STEMS = frozenset({"snapshot", "lanes", "flags", "stress", "timeseries"})


class DriftBlocked(RuntimeError):
    """A CORE sidecar failed its contract — the measured spine must not ship broken."""


def demote_drifted(data_dir: Path, *, core_stems: frozenset[str] = CORE_STEMS) -> dict:
    """Graceful-rot self-demotion (the metabolism). A CONTEXT/SIGNAL sidecar that fails its
    contract is DELETED from the served dir so its layer goes dark — the frontend already
    degrades-to-absent, so a rotted feed disappears instead of rendering broken, with zero
    human intervention. A CORE sidecar failure is collected as `blocked` (the caller raises:
    a broken spine must fail the run). A `demotions.json` record is written when anything is
    demoted, so the rot is LOUD (the Source Ledger surfaces it), never silent."""
    data_dir = Path(data_dir)
    demoted: list[dict] = []
    blocked: list[dict] = []
    for stem in sorted(SIDECAR_CONTRACTS):
        p = data_dir / f"{stem}.json"
        if not p.exists():
            continue
        v = check_file(p)
        if not v:
            continue
        if stem in core_stems:
            blocked.append({"stem": stem, "violations": v})
        else:
            p.unlink()  # go dark — the frontend hides an absent layer
            demoted.append({"stem": stem, "violations": v})
    # MERGE into demotions.json, never clobber it. This writer owns only the contracted
    # stems (SIDECAR_CONTRACTS); the reasoner records its own DERIVED ai_briefing demotion
    # into the SAME file one step earlier (reason._demote_briefing, refresh.yml). A blind
    # write_text would erase that foreign receipt whenever any contracted feed also drifts
    # — the layer would go dark with no receipt, exactly when the metabolism is busiest. So
    # preserve foreign-stem entries, recompute this run's owned stems fresh (a recovered
    # contracted feed thus drops its stale entry), and clear the file when nothing is dark.
    pth = data_dir / "demotions.json"
    try:
        existing = json.loads(pth.read_text()).get("demoted", []) if pth.exists() else []
    except (OSError, ValueError):
        existing = []
    foreign = [d for d in existing if d.get("stem") not in SIDECAR_CONTRACTS]
    merged = foreign + demoted
    if merged:
        pth.write_text(
            json.dumps(
                {
                    "note": "Feeds auto-demoted to dark because they failed their data contract "
                    "(schema/liveness drift). Demotion is automatic + loud, never silent.",
                    "demoted": merged,
                },
                indent=2,
            )
            + "\n"
        )
    elif pth.exists():
        pth.unlink()  # nothing demoted anywhere — leave no stale receipt behind
    return {"checked": len(SIDECAR_CONTRACTS), "demoted": demoted, "blocked": blocked}


def main(argv: list[str] | None = None) -> int:
    """CLI: validate a data dir, print a report, exit 1 on any schema/liveness drift. Missing
    sidecars are reported as warnings (a feed can transiently degrade-to-absent) but do not
    fail on their own — a *contracted, present, malformed* feed is the hard failure."""
    args = argv if argv is not None else sys.argv[1:]

    # --demote: self-heal mode (the metabolism). Quarantine drifted CONTEXT/SIGNAL feeds to
    # dark, HARD-fail on a drifted CORE feed. Used in refresh.yml BEFORE commit so a rotted
    # feed disappears instead of shipping broken — survives untended.
    if args and args[0] == "--demote":
        data_dir = Path(args[1]) if len(args) > 1 else publish_dir()
        report = demote_drifted(data_dir)
        print(f"self-demotion check over {data_dir}:")
        for d in report["demoted"]:
            print(f"  ⤓ demoted to dark: {d['stem']} — {d['violations']}")
        for b in report["blocked"]:
            print(f"  ✗ BLOCKED (core spine broke): {b['stem']} — {b['violations']}")
        if report["blocked"]:
            print("  publish blocked — a broken measured spine must not ship.")
            return 1
        if not report["demoted"]:
            print("  ✓ all feeds healthy")
        return 0

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
