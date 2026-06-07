"""Freight transport-cost anomaly — a measured SIGNAL we own (P3).

The price-side companion to the macro volume signal: the raw observed input is a cited
public-domain BLS Producer Price Index for each freight mode (long-distance truckload, rail
line-haul, deep-sea, air, warehousing); the number WE own is its 12-month rolling z-score.
We show OUR anomaly, never restate the index as ours (G0). The family enrolls in the FDR
gate. Keyless FRED public-domain series, by explicit allowlist.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from . import _http
from .commodities import parse_series, zscore_12mo, zscore_series  # the generic z helpers (DRY)
from .multiplicity import control_z

log = logging.getLogger(__name__)

# Public-domain FRED series (BLS Producer Price Index by freight mode). Monthly indices.
FRED_FREIGHT_RATE: tuple[tuple[str, str, str], ...] = (
    ("PCU484121484121", "Truckload freight rate", "PPI"),
    ("PCU482111482111", "Rail line-haul freight rate", "PPI"),
    ("PCU483111483111", "Deep-sea freight rate", "PPI"),
    ("PCU481111481111", "Air freight rate", "PPI"),
    ("PCU493110493110", "Warehousing & storage rate", "PPI"),
)

_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
_UA = "freight-radar/0.1 (+portfolio)"


def compute_signal(series_by_id: dict[str, list[tuple[str, float]]], q: float = 0.10) -> dict:
    """From {fred_id: [(date,value)]} compute each mode's owned z + FDR significance."""
    rows = []
    for fid, name, unit in FRED_FREIGHT_RATE:
        series = series_by_id.get(fid) or []
        z = zscore_12mo([v for _, v in series])
        if z is None or not series:
            continue
        rows.append(
            {
                "id": fid,
                "name": name,
                "unit": unit,
                "latest_value": round(series[-1][1], 2),
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
        "source": "FRED (public domain · BLS Producer Price Index)",
        "source_url": "https://fred.stlouisfed.org",
        "method": "12-month rolling z-score we compute over the cited monthly PPI",
        "disclaimer": (
            "The z-score is the anomaly WE compute; the index is shown as published, not "
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
    """Enricher entrypoint: fetch the allowlisted PPI series, compute our signal, write it."""
    series_by_id: dict[str, list[tuple[str, float]]] = {}
    try:
        with _http.client(headers={"User-Agent": _UA}) as client:
            for fid, _name, _unit in FRED_FREIGHT_RATE:
                try:
                    r = _http.get(client, _BASE + fid)
                    r.raise_for_status()
                    series_by_id[fid] = parse_series(r.text)
                except Exception as e:  # noqa: BLE001 — one bad series never sinks the layer
                    log.warning("freight_rate: %s failed: %r", fid, e)
    except Exception as e:  # noqa: BLE001 — degrade to absent (offline / CI)
        return {"name": "freight_rate", "sidecar": "freight_rate.json", "error": repr(e)}

    payload = compute_signal(series_by_id)
    if not payload["items"]:
        return {"name": "freight_rate", "sidecar": "freight_rate.json", "error": "no series"}
    payload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (ctx.out_dir / "freight_rate.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {
        "name": "freight_rate",
        "sidecar": "freight_rate.json",
        "series": len(payload["items"]),
        "significant": payload["counts"]["significant"],
    }
