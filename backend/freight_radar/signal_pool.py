"""Pooled FDR across ALL measured signal families — one multiplicity control, not per-silo.

Each signal family (commodities / macro / metals / freight_rate) today runs its own
Benjamini-Hochberg correction over its own small basket. That means "significant" is a
different bar in each silo: a weak anomaly can clear a 5-test family yet would never survive
against the full ~25-test universe. This pools every signal's z into ONE family — one m, one
q — so "significant" means exactly one thing platform-wide. It writes ``signals_fdr.json``,
the authoritative cross-family view the Board + the headline read. Significant is still only
an ANOMALY WE COMPUTED — never a cause, never a forecast.
"""

from __future__ import annotations

import json
from pathlib import Path

from .multiplicity import control_z

# the measured SIGNAL families (registry kind=SIGNAL, the FRED-z loop). gatun/exposure are
# self-contained measured signals with their own bespoke shape, not z-baskets — excluded.
SIGNAL_STEMS: tuple[str, ...] = (
    "commodities",
    "macro",
    "metals",
    "freight_rate",
    "slack",
    "labor",
)


def pool_signals(data_dir: Path, q: float = 0.10) -> dict:
    """Pool every signal family's z into one BH family. Returns the cross-family artifact."""
    data_dir = Path(data_dir)
    rows: list[dict] = []
    families: list[str] = []
    for stem in SIGNAL_STEMS:
        p = data_dir / f"{stem}.json"
        if not p.exists():
            continue
        try:
            payload = json.loads(p.read_text())
        except (OSError, ValueError):
            continue
        families.append(stem)
        # provenance lives at the FILE level (one source/url/method per family), not per item —
        # read it once and stamp it onto every row so each pooled signal stays click-to-traceable.
        src = payload.get("source")
        src_url = payload.get("source_url")
        method = payload.get("method")
        for it in payload.get("items", []):
            z = it.get("our_zscore")
            if z is None:
                continue
            rows.append(
                {
                    "family": stem,
                    "id": it.get("id"),
                    "name": it.get("name"),
                    "unit": it.get("unit"),
                    "as_of": it.get("as_of"),
                    "value": it.get("latest_value", it.get("latest_price")),
                    "our_zscore": z,
                    # the full raw->computed->published->cited chain, carried through the pool so
                    # the richest measured tier is finally traceable at the point (P0-A).
                    "source": src,  # RAW cited index (e.g. "FRED — BLS PPI")
                    "source_url": src_url,  # canonical home of the cited series
                    "method": method,  # the z-score WE compute (never the cited source's claim)
                    "z_series": it.get("z_series"),  # 36-pt computed anomaly track
                    # every signal here is national/global — no lat/lon, never place-attributable.
                    # P2-A's place panels read this to keep them in a structurally-fenced band.
                    "fenced": "national",
                }
            )

    keep, fdr = control_z([r["our_zscore"] for r in rows], q=q)
    for r, sig in zip(rows, keep):
        r["fdr_significant"] = bool(sig)  # POOLED significance, the authoritative one
    rows.sort(key=lambda r: abs(r["our_zscore"] or 0), reverse=True)
    return {
        "method": (
            "Benjamini-Hochberg FDR pooled across ALL measured signal families (one m, one q) — "
            "'significant' means significant across the whole signal universe, not within a silo"
        ),
        "disclaimer": (
            "A significant signal is an ANOMALY WE COMPUTED in the cited index — never a stated "
            "cause and never a forecast. Co-movement is association only."
        ),
        "q": q,
        "families": families,
        "counts": {
            "tested": fdr.n_tested,
            "significant": fdr.n_significant,
            "expected_false": fdr.expected_false,
        },
        "items": rows,
    }


def write(data_dir: Path, q: float = 0.10) -> Path | None:
    """Materialize signals_fdr.json. Returns the path, or None when no signal family is present
    (e.g. the hermetic golden run with network blocked) — nothing to pool, nothing written."""
    out = Path(data_dir)
    payload = pool_signals(out, q=q)
    if not payload["items"]:
        return None
    p = out / "signals_fdr.json"
    p.write_text(json.dumps(payload, separators=(",", ":")) + "\n")
    return p


def main(argv: list[str] | None = None) -> int:
    import sys

    from .config import publish_dir

    args = argv if argv is not None else sys.argv[1:]
    data_dir = Path(args[0]) if args else publish_dir()
    payload = pool_signals(data_dir)
    c = payload["counts"]
    print(
        f"pooled FDR over {len(payload['families'])} families: "
        f"{c['tested']} tested · {c['significant']} significant · expect <= {c['expected_false']} false"
    )
    for r in payload["items"]:
        mark = "✓" if r["fdr_significant"] else " "
        print(f"  [{mark}] {r['family']:13} {r['name'][:28]:28} z={r['our_zscore']:+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
