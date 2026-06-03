"""Wave 5: flag lifecycle — new / ongoing / escalated / resolved with hysteresis.

``fct_flags`` persists across runs, so each detection can be compared to the most
recent prior state to label how a flag is *moving*:

    new        flag_id never seen before
    ongoing    seen before, severity roughly unchanged (within the hysteresis band)
    escalated  seen before, severity rose by more than ``escalate_margin``
    resolved   a previously-active flag whose entity no longer trips this run —
               re-emitted ONCE with its severity decayed (``resolve_decay``), then
               it disappears (it won't be "active" next run to resolve again)

Hysteresis: ``escalate_margin`` (default +10) is a dead-band so a flag wobbling a
few severity points around threshold stays ``ongoing`` instead of thrashing
new/escalated/resolved every run. A drop in severity is never an escalation; it
stays ``ongoing`` (the flag is still active, just calmer).

Continuity is matched on ``flag_id`` (stable per kind|portid|ISO-week) first, and
falls back to ``(kind, portid)`` so a flag that rolls into a new ISO week — and
thus gets a fresh id — is still recognised as the *same* ongoing anomaly rather
than a brand-new one.
"""

from __future__ import annotations

from dataclasses import replace

from .detectors import DetectionConfig, Flag

NEW, ONGOING, ESCALATED, RESOLVED = "new", "ongoing", "escalated", "resolved"


def _prior_key(kind: str, portid: str) -> tuple[str, str]:
    return (kind, portid)


def apply_lifecycle(
    flags: list[Flag],
    prior: dict[str, dict],
    cfg: DetectionConfig,
) -> list[Flag]:
    """Label each current flag's ``lifecycle`` and append resolved-flag tombstones.

    ``prior`` maps prior ``flag_id`` -> a row dict with at least
    ``{severity, kind, portid, entity, lat, lon, ...}`` (the previously-active
    flags from ``fct_flags``). Returns a new list: the current flags relabeled,
    plus one ``resolved`` tombstone per prior active flag whose (kind, portid) no
    longer appears in the current set.

    Resolved tombstones reuse the prior row's identity and brief, set lifecycle to
    ``resolved``, and decay severity by ``resolve_decay`` so the rail visibly winds
    a cleared anomaly down rather than yanking it out.
    """
    # index prior by both flag_id and (kind, portid) for continuity matching.
    prior_by_id = prior
    prior_by_kp = {_prior_key(r["kind"], r["portid"]): r for r in prior.values()}
    current_kp = {_prior_key(f.kind, f.portid) for f in flags}

    out: list[Flag] = []
    for f in flags:
        seen = prior_by_id.get(f.flag_id) or prior_by_kp.get(_prior_key(f.kind, f.portid))
        if seen is None:
            out.append(replace(f, lifecycle=NEW))
            continue
        prev_sev = int(seen["severity"])
        if f.severity > prev_sev + cfg.escalate_margin:
            out.append(replace(f, lifecycle=ESCALATED))
        else:
            out.append(replace(f, lifecycle=ONGOING))

    # resolved tombstones: prior active flags whose entity no longer trips.
    for r in prior.values():
        if _prior_key(r["kind"], r["portid"]) in current_kp:
            continue
        if r.get("lifecycle") == RESOLVED:
            continue  # already tombstoned in a prior run; don't re-resolve forever
        out.append(_resolved_tombstone(r, cfg))
    return out


def _resolved_tombstone(row: dict, cfg: DetectionConfig) -> Flag:
    """Build a one-shot ``resolved`` Flag from a prior ``fct_flags`` row dict."""
    decayed = int(round(int(row["severity"]) * cfg.resolve_decay))
    note = "\n\n_Resolved: this anomaly no longer trips detection; severity decaying._"
    return Flag(
        flag_id=str(row["flag_id"]),
        kind=str(row["kind"]),
        entity=str(row["entity"]),
        portid=str(row["portid"]),
        lat=_f(row.get("lat")),
        lon=_f(row.get("lon")),
        severity=decayed,
        headline=f"[Resolved] {row['headline']}",
        brief_md=str(row["brief_md"]) + note,
        metric=str(row["metric"]),
        value=_f(row.get("value")) or 0.0,
        baseline=_f(row.get("baseline")) or 0.0,
        pct_change=_f(row.get("pct_change")) or 0.0,
        zscore=_f(row.get("zscore")) or 0.0,
        as_of=_iso_date(row["as_of"]),
        lifecycle=RESOLVED,
    )


def _iso_date(v) -> str:
    """Normalise a date / datetime / Timestamp / 'YYYY-MM-DD[...]' to 'YYYY-MM-DD'.

    DuckDB round-trips the DATE column back through pandas as a Timestamp, whose
    str() carries a time component — the upsert's ``date.fromisoformat`` rejects
    that, so coerce to the bare ISO date here.
    """
    if hasattr(v, "date") and not isinstance(v, str):
        return v.date().isoformat()
    return str(v)[:10]


def _f(v) -> float | None:
    """Coerce a possibly-None / numpy value to float, preserving None."""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
