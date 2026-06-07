"""hyp/associate.py — the quarantined ML association tier (the plan's subtlest, most dangerous).

A model-free pass that mines LEAD-LAG correlations between the measured SIGNAL z-series already
in fct_observation, controls the whole family with one Benjamini-Hochberg gate, and emits the
survivors as DARK association objects to ``data/hyp/``. It is, by construction, NOT a forecast
and NOT a cause: each row carries the stat method, the effect size, the n, and a mandatory
confounder note. The honest danger here is that macro signals all co-move with the business
cycle, so most "significant" pairs are a common driver, not a relationship — which is exactly
why the family is BH-controlled and every row is stamped association-only.

DARK: this artifact lives in ``data/hyp/`` and is exposed ONLY in the SQL console / agent
surface — never on the globe (a rendering + import fence enforces that in CI). This module is
quarantined like derived/: nothing in the package imports it; refresh.yml runs it as a
subprocess. It depends only on the substrate Parquet + stdlib + scipy — never the fact path.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..multiplicity import benjamini_hochberg

MAX_LAG = 3  # months
MIN_N = 18  # need a real overlap before a correlation means anything
TOP_K = 40  # cap the DARK roster; we log if we truncate
CONFOUNDER = (
    "Measured signals co-move with the global business cycle / aggregate demand; this is "
    "co-movement, NOT evidence either series drives the other. Association only, never a cause."
)


def _add_months(d: str, lag: int) -> str:
    y, m, day = int(d[:4]), int(d[5:7]), int(d[8:10])
    m0 = (y * 12 + (m - 1)) + lag
    return f"{m0 // 12:04d}-{m0 % 12 + 1:02d}-{day:02d}"


def _pearson(xs: list[float], ys: list[float]) -> tuple[float, float] | None:
    # local import so the module loads even if scipy is unavailable in a thin env
    try:
        from scipy.stats import pearsonr
    except Exception:  # noqa: BLE001
        return None
    n = len(xs)
    if n < 3 or len(set(xs)) < 2 or len(set(ys)) < 2:
        return None
    try:
        r, p = pearsonr(xs, ys)
    except Exception:  # noqa: BLE001
        return None
    if r != r or p != p:  # nan
        return None
    return float(r), float(p)


def _signal_series(parquet_path) -> dict[str, dict[str, float]]:
    import duckdb

    con = duckdb.connect()
    try:
        rows = con.execute(
            "SELECT entity_key, CAST(date_key AS VARCHAR), value "
            "FROM read_parquet(?) WHERE tier='SIGNAL'",
            [str(parquet_path)],
        ).fetchall()
    finally:
        con.close()
    out: dict[str, dict[str, float]] = {}
    for ek, dt, v in rows:
        out.setdefault(ek, {})[dt[:10]] = float(v)
    return out


def associate(parquet_path, q: float = 0.10) -> dict:
    """Mine lead-lag correlations across the signal z-series; BH-control the whole family."""
    series = _signal_series(parquet_path)
    sigs = sorted(series)
    cands: list[dict] = []
    for i in range(len(sigs)):
        for j in range(i + 1, len(sigs)):
            a, b = series[sigs[i]], series[sigs[j]]
            for lag in range(-MAX_LAG, MAX_LAG + 1):
                xs, ys = [], []
                for t, za in a.items():
                    shifted = b.get(_add_months(t, lag))
                    if shifted is not None:
                        xs.append(za)
                        ys.append(shifted)
                if len(xs) < MIN_N:
                    continue
                rp = _pearson(xs, ys)
                if rp is None:
                    continue
                r, p = rp
                cands.append(
                    {
                        "layer_a": sigs[i],
                        "layer_b": sigs[j],
                        "lag": lag,
                        "method": "lead_lag",
                        "effect_size": round(r, 3),
                        "p": p,
                        "n": len(xs),
                        "confounder_note": CONFOUNDER,
                    }
                )
    keep = benjamini_hochberg([c["p"] for c in cands], q=q)
    survivors = [c for c, k in zip(cands, keep) if k]
    survivors.sort(key=lambda c: abs(c["effect_size"]), reverse=True)
    truncated = max(0, len(survivors) - TOP_K)
    for c in survivors:
        c["p"] = round(c["p"], 4)
    return {
        "tier": "HYP",
        "method": "pairwise lead-lag Pearson correlation over the measured signal z-series",
        "disclaimer": (
            "DARK / quarantined. These are BH-controlled co-movements WE measured — never a "
            "forecast, never a cause. Most macro signals share a business-cycle driver; an "
            "association is not a relationship. Shown only in the data console, never on the globe."
        ),
        "q": q,
        "counts": {
            "tested": len(cands),
            "significant": len(survivors),
            "expected_false": round(q * len(survivors), 2),
            "truncated_from_display": truncated,
        },
        "items": survivors[:TOP_K],
    }


def write(parquet_path, out_dir) -> Path | None:
    """Materialize data/hyp/associations.json. Returns None if there's no signal series yet."""
    parquet_path = Path(parquet_path)
    if not parquet_path.exists():
        return None
    payload = associate(parquet_path)
    hyp = Path(out_dir) / "hyp"
    hyp.mkdir(parents=True, exist_ok=True)
    pth = hyp / "associations.json"
    pth.write_text(json.dumps(payload, indent=2) + "\n")
    return pth


def main(argv: list[str] | None = None) -> int:
    import sys

    from ..config import publish_dir

    args = argv if argv is not None else sys.argv[1:]
    out = Path(args[0]) if args else publish_dir()
    p = write(out / "store" / "fct_observation.parquet", out)
    if p is None:
        print("hyp: no signal series in the substrate yet — nothing to associate")
        return 0
    payload = json.loads(p.read_text())
    c = payload["counts"]
    print(f"hyp: {c['tested']} pairs×lags tested · {c['significant']} BH-significant (DARK) -> {p}")
    for it in payload["items"][:8]:
        print(f"  {it['layer_a']} ~ {it['layer_b']} (lag {it['lag']:+d}): r={it['effect_size']:+.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
