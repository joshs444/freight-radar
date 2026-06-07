"""Commodity-price anomaly — a measured SIGNAL we own (P3).

The clean promotion the plan describes (§5 P3, the G0–G5 gates): the raw observed input is a
cited public commodity price; the *number we own* is a 12-month rolling **z-score** we compute
in Python over it. We show OUR anomaly, never restate the source's price as ours (that would be
authority-laundering — G0). The family of z-scores enrolls in the FDR gate (multiplicity.py) so
a basket of commodities doesn't manufacture "anomalies". It is a SIGNAL, not the freight spine:
self-contained, association-only, and it never bridges into the freight detector.

Source: FRED public-domain commodity series (IMF Primary Commodity Prices) — keyless, by an
explicit allowlist (not a comment), per the critic. Degrades to absent on any failure.
"""

from __future__ import annotations

import json
import logging
import statistics
from datetime import datetime, timezone

from . import _http
from .multiplicity import control_z

log = logging.getLogger(__name__)

# Explicit public-domain allowlist (FRED series id -> name, unit). These are IMF Primary
# Commodity Prices redistributed by FRED in the public domain — no proprietary index here.
FRED_COMMODITIES: tuple[tuple[str, str, str], ...] = (
    ("POILBREUSDM", "Brent crude oil", "$/bbl"),
    ("PNGASEUUSDM", "Natural gas (EU)", "$/mmbtu"),
    ("PCOPPUSDM", "Copper", "$/mt"),
    ("PWHEAMTUSDM", "Wheat", "$/mt"),
    ("PMAIZMTUSDM", "Maize (corn)", "$/mt"),
    ("PSOYBUSDM", "Soybeans", "$/mt"),
)

_BASE = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
_UA = "freight-radar/0.1 (+portfolio)"


def parse_series(text: str) -> list[tuple[str, float]]:
    """FRED CSV ('observation_date,VALUE') -> chronological (date, value), missing dropped."""
    out: list[tuple[str, float]] = []
    for ln in text.splitlines()[1:]:
        if "," not in ln:
            continue
        d, v = ln.split(",", 1)
        v = v.strip()
        if v in (".", ""):
            continue
        try:
            out.append((d.strip(), float(v)))
        except ValueError:
            continue
    return out


def zscore_12mo(values: list[float]) -> float | None:
    """OUR owned scalar: the latest month's z vs the trailing 12 months.

    z = (x_t − mean(x_{t−12..t−1})) / stdev(x_{t−12..t−1}). Returns None when there isn't a
    full 12-month baseline or the baseline is flat (an undefined anomaly, never a fake 0).
    """
    if len(values) < 13:
        return None
    baseline = values[-13:-1]
    sd = statistics.stdev(baseline)
    if sd == 0:
        return None
    return (values[-1] - statistics.mean(baseline)) / sd


def zscore_series(series: list[tuple[str, float]], last_n: int = 36) -> list[dict]:
    """The SAME owned scalar (12-mo rolling z), computed at EVERY month — the last `last_n`
    points. This is the time series the signals-board sparkline draws and the hyp_* lead-lag
    read consumes; [] when the series is too short for one full baseline."""
    vals = [v for _, v in series]
    out: list[dict] = []
    for i in range(12, len(vals)):
        baseline = vals[i - 12 : i]
        sd = statistics.stdev(baseline)
        if sd == 0:
            continue
        out.append({"date": series[i][0], "z": round((vals[i] - statistics.mean(baseline)) / sd, 2)})
    return out[-last_n:]


def compute_signal(series_by_id: dict[str, list[tuple[str, float]]], q: float = 0.10) -> dict:
    """Pure: from {fred_id: [(date,value)]} compute each commodity's owned z + FDR significance."""
    rows = []
    for fid, name, unit in FRED_COMMODITIES:
        series = series_by_id.get(fid) or []
        vals = [v for _, v in series]
        z = zscore_12mo(vals)
        if z is None or not series:
            continue
        rows.append(
            {
                "id": fid,
                "name": name,
                "unit": unit,
                "latest_price": round(series[-1][1], 4),
                "as_of": series[-1][0],
                "our_zscore": round(z, 2),
                "z_series": zscore_series(series),
            }
        )
    keep, fdr = control_z([r["our_zscore"] for r in rows], q=q)
    for r, sig in zip(rows, keep):
        r["fdr_significant"] = bool(sig)
    rows.sort(key=lambda r: abs(r["our_zscore"]), reverse=True)
    as_of = max((r["as_of"] for r in rows), default="")
    return {
        "as_of": as_of,
        "source": "FRED (public domain · IMF Primary Commodity Prices)",
        "source_url": "https://fred.stlouisfed.org",
        "method": "12-month rolling z-score we compute over the cited monthly price",
        "disclaimer": (
            "The z-score is the anomaly WE compute; the price is shown as published, not "
            "restated as ours. Association only — never a stated cause of a freight movement."
        ),
        "counts": {
            "tested": fdr.n_tested,
            "significant": fdr.n_significant,
            "expected_false": fdr.expected_false,
        },
        "items": rows,
    }


def run(ctx) -> dict:
    """Enricher entrypoint: fetch the allowlisted FRED series, compute our signal, write it."""
    series_by_id: dict[str, list[tuple[str, float]]] = {}
    try:
        with _http.client(headers={"User-Agent": _UA}) as client:
            for fid, _name, _unit in FRED_COMMODITIES:
                try:
                    r = _http.get(client, _BASE + fid)
                    r.raise_for_status()
                    series_by_id[fid] = parse_series(r.text)
                except Exception as e:  # noqa: BLE001 — one bad series never sinks the layer
                    log.warning("commodities: %s failed: %r", fid, e)
    except Exception as e:  # noqa: BLE001 — degrade to absent (offline / CI)
        return {"name": "commodities", "sidecar": "commodities.json", "error": repr(e)}

    payload = compute_signal(series_by_id)
    if not payload["items"]:
        return {"name": "commodities", "sidecar": "commodities.json", "error": "no series"}
    payload["generated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    (ctx.out_dir / "commodities.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {
        "name": "commodities",
        "sidecar": "commodities.json",
        "commodities": len(payload["items"]),
        "significant": payload["counts"]["significant"],
    }
