"""Provenance-parity gate (P2-B) — the SSOT can never silently fork from the shipped data.

P0-B deleted the client-side URL regex and started STAMPING source_url + license onto flags (and
P0-A onto signals) from the registry root. Stamping freezes those URLs into the JSON at build time,
so a stale shipped data file could disagree with a regenerated catalog. This gate closes that hole:

  1. every flag's source_url + license == the registry-resolved ROOT Source (walk derives_from to
     snapshot; assert against registry.root_source — NOT catalog.json, which emits source=null for
     flags and would falsely pass),
  2. every signals_fdr item's source_url == its FAMILY layer's registry Source.url,
  3. the fenced national band is PLACE-INVARIANT (fence #1) — byte-identical for two distinct query
     points, a pure function of the global signals file.

Run as a DEPLOY-GATE in the weekly refresh (``python -m freight_radar.registry.parity <data_dir>``,
exit 1 on any violation) so stale stamped data can never ship; the same checks back the pytest gate
``tests/test_provenance_parity.py``.
"""

from __future__ import annotations

import json
from pathlib import Path

from .layers import root_source


def check(data_dir: Path) -> list[str]:
    """Return a list of human-readable parity violations ([] == clean)."""
    data_dir = Path(data_dir)
    problems: list[str] = []

    # (1) flags: source_url + license == the registry root (flags -> snapshot -> IMF PortWatch)
    flags_p = data_dir / "flags.json"
    if flags_p.exists():
        root = root_source("flags")
        if root is None:
            problems.append("registry: 'flags' has no resolvable root source")
        else:
            flags = json.loads(flags_p.read_text())
            for f in flags if isinstance(flags, list) else []:
                fid = f.get("flag_id")
                if f.get("source_url") != root.url:
                    problems.append(
                        f"flag {fid}: source_url {f.get('source_url')!r} != registry root {root.url!r}"
                    )
                if f.get("license") != root.license:
                    problems.append(
                        f"flag {fid}: license {f.get('license')!r} != registry root {root.license!r}"
                    )

    # (2) signals: each item's source_url == its family layer's registry Source.url
    sig_p = data_dir / "signals_fdr.json"
    if sig_p.exists():
        doc = json.loads(sig_p.read_text())
        for s in doc.get("items", []):
            fam = s.get("family")
            src = root_source(fam) if fam else None
            if src is None:
                problems.append(f"signal {s.get('id')}: family {fam!r} has no registry source")
            elif s.get("source_url") != src.url:
                problems.append(
                    f"signal {s.get('id')} ({fam}): source_url {s.get('source_url')!r} "
                    f"!= registry {src.url!r}"
                )

    # (3) the fenced national band must be place-INVARIANT (fence #1) — a pure function of the
    # global file, byte-identical for two distinct query points. (Deferred import avoids any
    # registry<->store import-time cycle.)
    from .. import store

    a = store.nearby(26.5, 56.2, 750.0, out_dir=data_dir).get("national_context")
    b = store.nearby(-33.9, 18.4, 1500.0, out_dir=data_dir).get("national_context")
    if a != b:
        problems.append("national_context is not place-invariant (fence #1 violated)")

    return problems


def main(argv: list[str] | None = None) -> int:
    import sys

    args = argv if argv is not None else sys.argv[1:]
    data_dir = Path(args[0]) if args else Path("frontend/public/data")
    problems = check(data_dir)
    if problems:
        print(f"PROVENANCE PARITY FAILED — {len(problems)} violation(s) in {data_dir}:")
        for p in problems[:50]:
            print("  ✗", p)
        if len(problems) > 50:
            print(f"  … and {len(problems) - 50} more")
        return 1
    print(
        "provenance parity OK — every stamped source_url/license matches the registry root; "
        "the national band is place-invariant"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
