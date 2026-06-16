"""CLI: run the detection brain over all entities and publish real flags.

    python -m freight_radar.detect.run_detection

Connects DuckDB -> loads each entity's daily series -> runs STL+rolling-z detection
-> upserts ``fct_flags`` (INSERT OR REPLACE, dedup-stable per ISO week) -> overwrites
``frontend/public/data/flags.json`` with the detected flags, severity-DESC. Prints a
receipt (counts by kind + the top-5 flags with their real numbers).
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, replace
from datetime import date, datetime
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ..config import DEFAULT_DB_PATH, REPO_ROOT
from ..ledger import prior_flags
from ..multiplicity import control_z

log = logging.getLogger(__name__)
from .cape_reroute import CAPE_CHOKEPOINTS, CAPE_KIND, detect_cape_reroute
from .detectors import (
    DetectionConfig,
    Flag,
    detect_series,
    load_config,
    make_flag_id,
    pct_vs_baseline,
)
from .holidays import apply_holiday_suppression
from .lifecycle import apply_lifecycle
from .persistent import detect_persistent

# Phase A2: the 5 leaf vessel types (they sum to portcalls_total). The dominant-
# cargo-type detector runs on the largest-share type so a move in (say) container
# calls is caught even when the blended total stays flat.
CARGO_TYPES = ("container", "tanker", "dry_bulk", "general_cargo", "roro")
CARGO_LABEL = {
    "container": "container", "tanker": "tanker", "dry_bulk": "dry-bulk",
    "general_cargo": "general-cargo", "roro": "RoRo",
}
MIN_DOMINANT_SHARE = 0.40  # only test a type that genuinely characterises the port

FLAGS_SCHEMA = Path(__file__).resolve().parent / "flags_schema.sql"
FLAGS_JSON = REPO_ROOT / "frontend" / "public" / "data" / "flags.json"

# Keys the frontend requires (export_snapshot.py Flag contract). asdict(Flag)
# already produces exactly this superset; we keep the order explicit for the file.
FLAG_KEYS = (
    "flag_id", "kind", "entity", "portid", "lat", "lon", "severity",
    "headline", "brief_md", "metric", "value", "baseline", "pct_change",
    "zscore", "as_of", "source", "source_url", "license", "method", "lifecycle",
)


NATIONAL_DEP_MIN = 25.0  # only annotate a flag when the port is materially systemic


def _econ_weights(
    vessel_counts: pd.Series, national_share: pd.Series | None = None
) -> dict[str, float]:
    """Map portid -> 0.6..1.0 severity weight.

    Base is the vessel_count_total percentile rank (a globally busier waterway weighs
    more). When ``national_share`` is given (ports — Phase B), it blends in the port's
    share of its COUNTRY's maritime trade (0-100 %): a sole-gateway port (Mombasa ≈
    99.8 % of Kenya's trade) is systemically critical even if globally mid-sized, so a
    disruption there should outrank an equally-busy port that is one of many in its
    country. National dependence contributes up to 30 % of the variable band.
    """
    pct = vessel_counts.rank(pct=True)  # 0..1
    if national_share is None:
        return {pid: 0.6 + 0.4 * float(p) for pid, p in pct.items()}
    nat = (national_share.fillna(0.0) / 100.0).clip(0.0, 1.0)
    return {
        pid: 0.6 + 0.4 * (0.7 * float(pct[pid]) + 0.3 * float(nat.get(pid, 0.0)))
        for pid in pct.index
    }


def _national_dependence_note(d: pd.Series, entity: str) -> str:
    """A cited markdown line for a port that carries a large share of its country's
    maritime trade — '' when below the threshold. Phase B's systemic-importance signal."""
    imp = float(d["share_country_maritime_import"]) if pd.notna(d.get("share_country_maritime_import")) else 0.0
    exp = float(d["share_country_maritime_export"]) if pd.notna(d.get("share_country_maritime_export")) else 0.0
    if max(imp, exp) < NATIONAL_DEP_MIN:
        return ""
    country = str(d["country"]) if pd.notna(d.get("country")) else "its country"
    sole = "A single-port dependency — " if max(imp, exp) >= 80 else ""
    return (
        f"\n\n_**{entity}** handles ~{imp:.0f}% of {country}'s maritime imports and "
        f"~{exp:.0f}% of its exports (IMF national-dependence share). {sole}disruption "
        f"here is systemically significant for {country}._"
    )


def _detect_chokepoints(con: duckdb.DuckDBPyConnection, cfg: DetectionConfig) -> list[Flag]:
    dims = con.execute(
        "SELECT portid, fullname, lat, lon, vessel_count_total FROM dim_chokepoint"
    ).df().set_index("portid")
    weights = _econ_weights(dims["vessel_count_total"])
    daily = con.execute(
        "SELECT portid, date, n_total, capacity_total "
        "FROM fct_chokepoint_daily ORDER BY portid, date"
    ).df()

    flags: list[Flag] = []
    series_by_id: dict[str, pd.Series] = {}
    cap_by_id: dict[str, pd.Series] = {}
    for portid, grp in daily.groupby("portid"):
        if portid not in dims.index:
            continue
        d = dims.loc[portid]
        idx = pd.to_datetime(grp["date"])
        series = pd.Series(grp["n_total"].to_numpy(), index=idx)
        series_by_id[portid] = series
        cap_by_id[portid] = pd.Series(grp["capacity_total"].to_numpy(), index=idx)
        flag = detect_series(
            portid=portid,
            entity=str(d["fullname"]),
            entity_type="chokepoint",
            metric="n_total",
            values=series,
            as_of=series.index[-1].date(),
            cfg=cfg,
            lat=float(d["lat"]) if pd.notna(d["lat"]) else None,
            lon=float(d["lon"]) if pd.notna(d["lon"]) else None,
            econ_weight=weights.get(portid, 1.0),
            unit="vessels",
        )
        if flag:
            flags.append(flag)

    # Persistent level-shift pass: catch sustained disruptions the fresh detector
    # (28-day baseline) has adapted to and now reads as "normal" (e.g. Hormuz).
    flagged = {f.portid for f in flags}
    for portid, series in series_by_id.items():
        if portid in flagged:
            continue
        d = dims.loc[portid]
        pf = detect_persistent(
            portid=portid,
            entity=str(d["fullname"]),
            values=series,
            cfg=cfg,
            lat=float(d["lat"]) if pd.notna(d["lat"]) else None,
            lon=float(d["lon"]) if pd.notna(d["lon"]) else None,
            econ_weight=weights.get(portid, 1.0),
            unit="vessels",
        )
        if pf:
            flags.append(pf)

    # Phase A3: avg-vessel-size pass for chokepoints the count detectors left calm.
    # Size (capacity_total / n_total) is orthogonal to the count (audit: corr -0.08 at
    # Gibraltar), so a shift to bigger/smaller transiting ships is a signal the count
    # can't see. One flag per portid, so only unflagged chokepoints are scanned.
    flagged = {f.portid for f in flags}
    for portid, series in series_by_id.items():
        if portid in flagged:
            continue
        d = dims.loc[portid]
        sf = _chokepoint_size_flag(
            portid,
            str(d["fullname"]),
            series,
            cap_by_id[portid],
            cfg,
            lat=float(d["lat"]) if pd.notna(d["lat"]) else None,
            lon=float(d["lon"]) if pd.notna(d["lon"]) else None,
            econ_weight=weights.get(portid, 1.0),
        )
        if sf:
            flags.append(sf)
    return flags


def _chokepoint_size_flag(
    portid: str,
    entity: str,
    n_series: pd.Series,
    cap_series: pd.Series,
    cfg: DetectionConfig,
    *,
    lat: float | None,
    lon: float | None,
    econ_weight: float,
) -> Flag | None:
    """Phase A3: a shift in the AVERAGE size of transiting vessels (capacity_total /
    n_total, in DWT) that the transit-count detectors didn't catch. Returns a
    ``chokepoint_vessel_size_shift`` Flag or None.

    Honest framing: capacity_total is a *flow* (summed DWT of vessels that transited),
    so capacity/count is the mean vessel size — NOT capacity utilisation (there is no
    ceiling to divide by; the audit explicitly forbade an n/capacity %). The brief
    contrasts the size move against the (calm) transit count at the same day.
    """
    df = pd.concat([n_series.rename("n"), cap_series.rename("cap")], axis=1).sort_index()
    n = df["n"].to_numpy(dtype=float)
    cap = df["cap"].to_numpy(dtype=float)
    size = np.divide(cap, n, out=np.full_like(cap, np.nan), where=n > 0)  # NULLIF(n,0)
    size_series = pd.Series(size, index=df.index).dropna()
    if len(size_series) < cfg.min_history_days:
        return None

    base = detect_series(
        portid=portid,
        entity=entity,
        entity_type="chokepoint",
        metric="avg_vessel_size_dwt",
        values=size_series,
        as_of=size_series.index[-1].date(),
        cfg=cfg,
        lat=lat,
        lon=lon,
        econ_weight=econ_weight,
        unit="DWT",
    )
    if base is None:
        return None

    # the transit count at the SAME peak day — the orthogonality this detector exists
    # to expose (count calm, ship size moved).
    n_clean = n_series.sort_index()
    pos = int(n_clean.index.get_indexer([pd.Timestamp(base.as_of)])[0])
    if pos < 0:
        pos = len(n_clean) - 1
    _, _, count_pct = pct_vs_baseline(n_clean, cfg.z_window, end=pos)

    direction = "down" if base.pct_change < 0 else "up"
    rel = "below" if direction == "down" else "above"
    verb = "fell" if direction == "down" else "rose"
    sized = "smaller" if direction == "down" else "larger"
    peak_date = date.fromisoformat(base.as_of)
    headline = f"{entity} avg vessel size {abs(base.pct_change):.0f}% {rel} norm — {sized} ships"
    brief = (
        f"**{entity}** average transiting **vessel size** {verb} to "
        f"**~{base.value:,.0f} DWT** on {base.as_of}, **{abs(base.pct_change):.0f}% "
        f"{rel}** its 28-day norm of ~{base.baseline:,.0f} DWT (z = {base.zscore:+.1f}) "
        f"— {sized} ships on average — while the **transit count** stayed near normal "
        f"({count_pct:+.0f}%). The count detector can't see this; ship-size is "
        f"orthogonal to ship-count.\n\n"
        f"_Average size = transiting capacity (DWT) ÷ vessel count — a fleet-mix shift, "
        f"**not** capacity utilisation (capacity here is a flow, not a ceiling)._\n\n"
        f"_Method: {base.method}. Source: {base.source}._"
    )
    return replace(
        base,
        flag_id=make_flag_id("chokepoint_vessel_size_shift", portid, peak_date),
        kind="chokepoint_vessel_size_shift",
        headline=headline,
        brief_md=brief,
    )


def _detect_ports(con: duckdb.DuckDBPyConnection, cfg: DetectionConfig) -> list[Flag]:
    dims = con.execute(
        """
        SELECT portid, portname, fullname, country, lat, lon, vessel_count_total,
               share_country_maritime_import, share_country_maritime_export
        FROM dim_port
        WHERE lat IS NOT NULL AND lon IS NOT NULL
        ORDER BY vessel_count_total DESC
        LIMIT ?
        """,
        [cfg.top_n_ports],
    ).df().set_index("portid")
    nat_share = dims[
        ["share_country_maritime_import", "share_country_maritime_export"]
    ].max(axis=1)
    weights = _econ_weights(dims["vessel_count_total"], national_share=nat_share)
    cargo_cols = ", ".join(f"portcalls_{t}" for t in CARGO_TYPES)
    daily = con.execute(
        f"""
        SELECT portid, date, portcalls_total, {cargo_cols}
        FROM fct_port_daily
        WHERE portid IN (SELECT portid FROM dim_port
                         WHERE lat IS NOT NULL AND lon IS NOT NULL
                         ORDER BY vessel_count_total DESC LIMIT ?)
        ORDER BY portid, date
        """,
        [cfg.top_n_ports],
    ).df()

    flags: list[Flag] = []
    n_tested = 0  # the FDR family size — every port we actually run the detector over
    for portid, grp in daily.groupby("portid"):
        if portid not in dims.index:
            continue
        n_tested += 1
        d = dims.loc[portid]
        name = str(d["portname"]) if pd.notna(d["portname"]) else str(d["fullname"])
        lat, lon = float(d["lat"]), float(d["lon"])
        econ_weight = weights.get(portid, 1.0)
        series = pd.Series(
            grp["portcalls_total"].to_numpy(), index=pd.to_datetime(grp["date"])
        )
        flag = detect_series(
            portid=portid,
            entity=name,
            entity_type="port",
            metric="portcalls_total",
            values=series,
            as_of=series.index[-1].date(),
            cfg=cfg,
            lat=lat,
            lon=lon,
            econ_weight=econ_weight,
            unit="port calls",
        )
        note = _national_dependence_note(d, name)  # Phase B systemic-importance line
        if flag:
            flags.append(replace(flag, brief_md=flag.brief_md + note) if note else flag)
            continue  # one flag per portid (the frontend keys flags by portid)
        # blended total stayed calm — look for a move in the dominant cargo type
        cargo = _dominant_cargo_flag(
            portid, name, grp, cfg, lat=lat, lon=lon, econ_weight=econ_weight
        )
        if cargo:
            flags.append(replace(cargo, brief_md=cargo.brief_md + note) if note else cargo)

    # Per-domain FDR (multiplicity control). Across ~2065 ports, a base |z|-gate alone
    # would manufacture ~5-6 pure-noise flags. Benjamini-Hochberg over the PORT family at
    # cfg.fdr_q keeps only the genuinely-significant anomalies — so going wide doesn't break
    # "these are real". The 28 chokepoints are a small, pre-registered family and are NOT
    # corrected here (a |z|≥3 there is meaningful; among 2065 ports it is likely noise).
    if flags:
        keep, fdr = control_z([abs(f.zscore) for f in flags], q=cfg.fdr_q, m=n_tested)
        kept = [f for f, k in zip(flags, keep) if k]
        log.info(
            "port FDR: tested %d ports, %d candidates, %d significant (q=%.2f, expect <=%.1f false)",
            n_tested,
            len(flags),
            len(kept),
            cfg.fdr_q,
            fdr.expected_false,
        )
        return kept
    return flags


def _dominant_cargo_flag(
    portid: str,
    name: str,
    grp: pd.DataFrame,
    cfg: DetectionConfig,
    *,
    lat: float,
    lon: float,
    econ_weight: float,
) -> Flag | None:
    """Phase A2: a move in the port's DOMINANT cargo type that the blended
    ``portcalls_total`` detector missed (e.g. container calls collapse while the
    overall total holds flat). Returns a ``port_cargo_type_{drop,spike}`` Flag or None.

    Only the largest-share type (>= ``MIN_DOMINANT_SHARE``) is tested, through the
    SAME gated ``detect_series`` pipeline as the blended detector — so it adds
    resolution without opening a new false-positive surface. The brief contrasts the
    type-specific move against the port's flat overall calls, which is precisely why a
    blended view misses it. Every number is from the per-type series; nothing invented.
    """
    means = {t: float(grp[f"portcalls_{t}"].mean()) for t in CARGO_TYPES}
    total_mean = sum(means.values())
    if total_mean <= 0:
        return None
    dtype = max(means, key=means.get)
    share = means[dtype] / total_mean
    if share < MIN_DOMINANT_SHARE:
        return None

    idx = pd.to_datetime(grp["date"])
    series = pd.Series(grp[f"portcalls_{dtype}"].to_numpy(), index=idx)
    base = detect_series(
        portid=portid,
        entity=name,
        entity_type="port",
        metric=f"portcalls_{dtype}",
        values=series,
        as_of=series.index[-1].date(),
        cfg=cfg,
        lat=lat,
        lon=lon,
        econ_weight=econ_weight,
        unit=f"{CARGO_LABEL[dtype]} calls",
    )
    if base is None:
        return None

    # Per-type pct vs each type's OWN 28-day norm at the same peak day — the
    # attribution a blended view erases. Computed identically to the main detector;
    # nothing invented. We report the dominant type's move against the next-largest
    # types (substantial base -> stable pct, no tiny-denominator noise).
    def _pct_at(col: str) -> float:
        s = pd.Series(grp[col].to_numpy(), index=idx).sort_index()
        pos = int(s.index.get_indexer([pd.Timestamp(base.as_of)])[0])
        if pos < 0:
            pos = len(s) - 1
        return pct_vs_baseline(s, cfg.z_window, end=pos)[2]

    others = sorted(
        ((t, means[t]) for t in CARGO_TYPES if t != dtype),
        key=lambda kv: kv[1], reverse=True,
    )
    contrast = ", ".join(
        f"{CARGO_LABEL[t]} {_pct_at(f'portcalls_{t}'):+.0f}%" for t, m in others[:2] if m > 0
    )
    total_pct = _pct_at("portcalls_total")

    label = CARGO_LABEL[dtype]
    direction = "drop" if base.pct_change < 0 else "spike"
    new_kind = f"port_cargo_type_{direction}"
    rel = "below" if base.pct_change < 0 else "above"
    verb = "fell" if direction == "drop" else "surged"
    peak_date = date.fromisoformat(base.as_of)
    headline = f"{name} {label} calls {abs(base.pct_change):.0f}% {rel} 28-day norm"
    brief = (
        f"**{name}** **{label}** port calls {verb} to **{base.value:.0f}/day** on "
        f"{base.as_of}, **{abs(base.pct_change):.0f}% {rel}** their 28-day norm of "
        f"~{base.baseline:.0f}/day (z = {base.zscore:+.1f})"
        + (f" — by type: {contrast}." if contrast else ".")
        + f"\n\n_{label.capitalize()} is this port's dominant type (~{share * 100:.0f}% "
        f"of calls). The blended port-calls total didn't trip the detector here "
        f"(total {total_pct:+.0f}% vs norm); isolating the dominant stream surfaces "
        f"the move. \"Drop/surge\" is inferred from daily port calls, not vessel "
        f"dwell-time data._\n\n"
        f"_Method: {base.method}. Source: {base.source}._"
    )
    return replace(
        base,
        flag_id=make_flag_id(new_kind, portid, peak_date),
        kind=new_kind,
        headline=headline,
        brief_md=brief,
    )


def _detect_cape_reroute(
    con: duckdb.DuckDBPyConnection, cfg: DetectionConfig
) -> list[Flag]:
    """Wave 5: one cape_reroute flag iff Red Sea is down while the Cape is up.

    Pulls the combined (summed) Suez+Bab daily series and the Cape series, joins on
    date so the windows align, and delegates to ``detect_cape_reroute``. Returns []
    when the data shows no divergence (the honest default on a calm window).
    """
    rs_ids = list(cfg.red_sea_portids)
    placeholders = ", ".join("?" for _ in rs_ids)
    rs = con.execute(
        f"""
        SELECT date, SUM(n_total) AS n_total
        FROM fct_chokepoint_daily
        WHERE portid IN ({placeholders})
        GROUP BY date ORDER BY date
        """,
        rs_ids,
    ).df()
    cape = con.execute(
        "SELECT date, n_total FROM fct_chokepoint_daily WHERE portid = ? ORDER BY date",
        [cfg.cape_portid],
    ).df()
    if rs.empty or cape.empty:
        return []
    geo = con.execute(
        "SELECT lat, lon FROM dim_chokepoint WHERE portid = ?", [cfg.cape_portid]
    ).fetchone()
    cape_lat = float(geo[0]) if geo and geo[0] is not None else None
    cape_lon = float(geo[1]) if geo and geo[1] is not None else None

    rs_s = pd.Series(rs["n_total"].to_numpy(), index=pd.to_datetime(rs["date"]))
    cape_s = pd.Series(cape["n_total"].to_numpy(), index=pd.to_datetime(cape["date"]))
    as_of = max(rs_s.index[-1], cape_s.index[-1]).date()
    flag = detect_cape_reroute(
        red_sea=rs_s,
        cape=cape_s,
        cape_lat=cape_lat,
        cape_lon=cape_lon,
        as_of=as_of,
        cfg=cfg,
    )
    return [flag] if flag else []


def _load_prior_flags(state_dir: Path | None = None) -> dict[str, dict]:
    """Most-recent prior flag state keyed by flag_id (for lifecycle), read from
    the committed flags ledger (``data/state/flags_ledger.jsonl``).

    The ledger is the ONLY prior-flags source: the weekly refresh rebuilds the
    DuckDB from scratch, so a ``fct_flags`` read-back always saw an empty table
    in production and every flag shipped as "new" — hysteresis and resolved
    tombstones never fired (ADR-0009). Rows come from the latest recorded run
    only, excluding already-resolved tombstones (so a cleared flag doesn't keep
    re-resolving). Empty on the first ever run. ``state_dir`` defaults to the
    repo's ``data/state/``, env-overridable so tests inject tmp dirs.
    """
    return prior_flags(state_dir)


def _upsert_flags(con: duckdb.DuckDBPyConnection, flags: list[Flag]) -> None:
    con.execute(FLAGS_SCHEMA.read_text())
    if not flags:
        return
    detected = date.today()
    now = datetime.now()
    rows = [
        {
            **asdict(f),
            "as_of": date.fromisoformat(f.as_of),
            "detected_date": detected,
            "computed_at": now,
        }
        for f in flags
    ]
    df = pd.DataFrame(rows)
    # source_url + license are static registry-resolved provenance (P0-B) carried in the flags.json
    # contract, NOT measured facts — they live on the Flag dataclass + the JSON, but fct_flags stays
    # the table of computed numbers. Project them out so the upsert matches the schema's columns.
    df = df.drop(columns=["source_url", "license"], errors="ignore")
    cols = ", ".join(f'"{c}"' for c in df.columns)
    con.register("_flags_src", df)
    try:
        con.execute(
            f"INSERT OR REPLACE INTO fct_flags ({cols}) SELECT {cols} FROM _flags_src"
        )
    finally:
        con.unregister("_flags_src")


def _write_json(flags: list[Flag], path: Path = FLAGS_JSON) -> None:
    flags_sorted = sorted(flags, key=lambda f: f.severity, reverse=True)
    payload = []
    for f in flags_sorted:
        d = asdict(f)
        row = {k: d[k] for k in FLAG_KEYS}
        if f.kind == CAPE_KIND:
            # H1-B: structured chokepoint refs. The cape flag's entity is a story
            # string ("Red Sea → Cape ..."), not a chokepoint name, so exposure
            # matches lanes on these instead. An OPTIONAL flags.json field carried
            # like source_url/license (see _upsert_flags) — fct_flags stays the
            # table of computed numbers.
            row["chokepoints"] = list(CAPE_CHOKEPOINTS)
        payload.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2))


def run(db_path=DEFAULT_DB_PATH, flags_json: Path | None = None) -> list[Flag]:
    """Detect, gate, label lifecycle, suppress holidays -> upsert + publish.

    Wave-5 pipeline (order matters): read the prior flag state from the committed
    ledger -> run the (change-point-gated) chokepoint/port detectors + the Cape-reroute
    detector -> downweight benign holiday dips -> label lifecycle (and emit resolved
    tombstones) -> upsert + write flags.json. Public API is unchanged: returns the
    final ``list[Flag]`` (now carrying real lifecycle labels), and the JSON keeps
    the ``FLAG_KEYS`` contract (plus an optional ``chokepoints`` ref on cape-reroute
    flags).
    """
    cfg = load_config()
    con = duckdb.connect(str(db_path))
    try:
        prior = _load_prior_flags()
        detected = (
            _detect_chokepoints(con, cfg)
            + _detect_ports(con, cfg)
            + _detect_cape_reroute(con, cfg)
        )
        detected = apply_holiday_suppression(detected, cfg)
        flags = apply_lifecycle(detected, prior, cfg)
        _upsert_flags(con, flags)
    finally:
        con.close()
    _write_json(flags, flags_json or FLAGS_JSON)
    return flags


def _receipt(flags: list[Flag]) -> None:
    by_kind: dict[str, int] = {}
    for f in flags:
        by_kind[f.kind] = by_kind.get(f.kind, 0) + 1
    print("=== detection receipt ===")
    print(f"  total flags: {len(flags)}")
    for kind, n in sorted(by_kind.items()):
        print(f"    {kind}: {n}")
    print(f"  flags.json: {FLAGS_JSON}")
    print("  top 5 by severity:")
    for f in sorted(flags, key=lambda x: x.severity, reverse=True)[:5]:
        print(
            f"    [{f.severity:3d}] {f.kind:28s} {f.entity:22s} "
            f"value={f.value:g} baseline={f.baseline:g} "
            f"pct={f.pct_change:+g}% z={f.zscore:+g} as_of={f.as_of}"
        )


if __name__ == "__main__":
    _receipt(run())
