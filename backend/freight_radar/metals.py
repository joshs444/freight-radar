"""Industrial-metals & bulk-energy anomaly — a measured SIGNAL we own (P3).

The dry-bulk side of the commodity signal: the raw observed input is a cited public-domain
IMF price (aluminum, iron ore, nickel, zinc, lead, tin, coal, the energy index — the metals
and bulk-energy that fill bulk carriers); the number WE own is its 12-month rolling z-score.
We show OUR anomaly, never restate the price as ours (G0). The family enrolls in the FDR gate.
Keyless FRED public-domain series, by explicit allowlist.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from . import _http
from .commodities import parse_series, zscore_12mo, zscore_series
from .multiplicity import control_z

log = logging.getLogger(__name__)

FRED_METALS: tuple[tuple[str, str, str], ...] = (
    ("PALUMUSDM", "Aluminum", "$/mt"),
    ("PIORECRUSDM", "Iron Ore", "$/mt"),
    ("PNICKUSDM", "Nickel", "$/mt"),
    ("PZINCUSDM", "Zinc", "$/mt"),
    ("PLEADUSDM", "Lead", "$/mt"),
    ("PTINUSDM", "Tin", "$/mt"),
    ("PCOALAUUSDM", "Coal (Australia)", "$/mt"),
    ("PNRGINDEXM", "Energy Index", "index"),
)

_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
_UA = "freight-radar/0.1 (+portfolio)"


def compute_signal(series_by_id: dict[str, list[tuple[str, float]]], q: float = 0.10) -> dict:
    rows = []
    for fid, name, unit in FRED_METALS:
        series = series_by_id.get(fid) or []
        z = zscore_12mo([v for _, v in series])
        if z is None or not series:
            continue
        rows.append(
            {
                "id": fid,
                "name": name,
                "unit": unit,
                "latest_price": round(series[-1][1], 2),
                "as_of": series[-1][0],
                "our_zscore": round(z, 2),
                "z_series": zscore_series(series),
            }
        )
    keep, fdr = control_z([r["our_zscore"] for r in rows], q=q)
    for r, sig in zip(rows, keep):
        r["fdr_significant"] = bool(sig)
    rows.sort(key=lambda r: abs(r["our_zscore"]), reverse=True)
    return {
        "as_of": max((r["as_of"] for r in rows), default=""),
        "source": "FRED (public domain · IMF Primary Commodity Prices)",
        "source_url": "https://fred.stlouisfed.org",
        "method": "12-month rolling z-score we compute over the cited monthly price",
        "disclaimer": (
            "The z-score is the anomaly WE compute; the price is shown as published, not "
            "restated as ours. Association only — never a stated cause."
        ),
        "counts": {
            "tested": fdr.n_tested,
            "significant": fdr.n_significant,
            "expected_false": fdr.expected_false,
        },
        "items": rows,
    }


def run(ctx) -> dict:
    series_by_id: dict[str, list[tuple[str, float]]] = {}
    try:
        with _http.client(headers={"User-Agent": _UA}) as client:
            for fid, _name, _unit in FRED_METALS:
                try:
                    r = _http.get(client, _BASE + fid)
                    r.raise_for_status()
                    series_by_id[fid] = parse_series(r.text)
                except Exception as e:  # noqa: BLE001 — one bad series never sinks the layer
                    log.warning("metals: %s failed: %r", fid, e)
    except Exception as e:  # noqa: BLE001 — degrade to absent (offline / CI)
        return {"name": "metals", "sidecar": "metals.json", "error": repr(e)}

    payload = compute_signal(series_by_id)
    if not payload["items"]:
        return {"name": "metals", "sidecar": "metals.json", "error": "no series"}
    payload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (ctx.out_dir / "metals.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {
        "name": "metals",
        "sidecar": "metals.json",
        "series": len(payload["items"]),
        "significant": payload["counts"]["significant"],
    }
