"""Wave 5: holiday demand-dip suppression.

Container traffic predictably sags around a handful of recurring windows — these
are benign seasonal dips, not crises, and left alone they flood the rail with
``*_drop`` / ``*_collapse`` false positives. During a configured window we
*downweight* (or drop) a flag whose direction is "down"; spikes are never touched.

Windows are matched by (month, day) so they recur every year and a window may wrap
the year boundary (e.g. Christmas 12-22 .. New Year 01-02). Configured in
``detection.yaml`` under ``holiday_windows``; documented dates:

    Lunar New Year        02-08 .. 02-20   (China factory shutdown)
    Christmas / New Year  12-22 .. 01-02   (Western demand lull, wraps year-end)
    Golden Week (China)   10-01 .. 10-07   (national holiday)

The suppression is *direction-aware and subtractive*: it can only lower a down
flag's severity (by ``holiday_downweight``; 0 = drop the flag), never raise one.
"""

from __future__ import annotations

from datetime import date

from .detectors import DetectionConfig, Flag


def _md(s: str) -> tuple[int, int]:
    """'MM-DD' -> (month, day)."""
    m, d = s.split("-")
    return int(m), int(d)


def in_holiday_window(day: date, cfg: DetectionConfig) -> str | None:
    """Name of the holiday window containing ``day`` (by month/day), else None.

    Year-wrapping windows (start month/day > end month/day) match either side of
    the new year. ``day``'s own year is irrelevant — only month/day matter.
    """
    key = (day.month, day.day)
    for name, start, end in cfg.holiday_windows:
        lo, hi = _md(start), _md(end)
        within = lo <= key <= hi if lo <= hi else (key >= lo or key <= hi)
        if within:
            return name
    return None


def is_drop_kind(kind: str) -> bool:
    """True for the down-direction flag kinds (collapse / drop). Spikes excluded."""
    return kind.endswith("_collapse") or kind.endswith("_drop")


def apply_holiday_suppression(flags: list[Flag], cfg: DetectionConfig) -> list[Flag]:
    """Downweight (or drop) benign down-flags whose ``as_of`` falls in a holiday.

    Returns a new list. A suppressed flag keeps every number it computed but has
    its severity multiplied by ``holiday_downweight`` and a one-line note appended
    to the brief; at downweight 0 the flag is dropped entirely. Up-flags and flags
    outside every window pass through untouched.
    """
    if not cfg.holiday_suppress or not cfg.holiday_windows:
        return flags
    out: list[Flag] = []
    from dataclasses import replace

    for f in flags:
        if not is_drop_kind(f.kind):
            out.append(f)
            continue
        win = in_holiday_window(date.fromisoformat(f.as_of), cfg)
        if win is None:
            out.append(f)
            continue
        if cfg.holiday_downweight <= 0:
            continue  # drop the benign dip entirely
        new_sev = int(round(f.severity * cfg.holiday_downweight))
        note = (
            f"\n\n_Severity downweighted: {f.as_of} falls within the "
            f"**{win}** demand-dip window — a seasonal lull, not a disruption._"
        )
        out.append(replace(f, severity=new_sev, brief_md=f.brief_md + note))
    return out
