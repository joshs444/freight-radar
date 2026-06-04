"""Weekly narrative brief — the "what's moving in ocean freight" hero card.

Assembles 3-6 plain-English bullets at publish time from the sidecars that already
exist (flags / stress / market / exposure / news / events). Every number in every
bullet is string-substituted from a real computed value — the prose is a template,
the figures are never invented. This is the deterministic-template approach the
README leans into: no model is called, so no model can hallucinate a statistic.

The brief also carries a "this week" read: detections in the trailing 7 days (by the
flag's own as_of) plus the born/escalated/resolved counts from the event ledger, so
a reader gets the delta, not just the standing state.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

WEEK = 7


def _load(out: Path, name: str):
    p = out / name
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def _money(n) -> str:
    if n is None:
        return "n/a"
    n = float(n)
    if abs(n) >= 1e9:
        return f"${n / 1e9:.1f}B"
    if abs(n) >= 1e6:
        return f"${n / 1e6:.1f}M"
    if abs(n) >= 1e3:
        return f"${n / 1e3:.0f}K"
    return f"${n:.0f}"


def _within_week(as_of: str, today: date) -> bool:
    try:
        return (today - date.fromisoformat(as_of)).days <= WEEK
    except (ValueError, TypeError):
        return False


def build(out: Path, today: date) -> dict:
    flags = _load(out, "flags.json") or []
    stress = _load(out, "stress.json") or {}
    market = _load(out, "market.json") or {}
    exposure = _load(out, "exposure.json") or {}
    events = _load(out, "events.json") or {}

    active = [f for f in flags if f.get("lifecycle") != "resolved"]
    bullets: list[dict] = []

    # 1) stress headline
    if stress.get("available"):
        wow = stress.get("wow_delta", 0)
        wd = stress.get("wow_direction", "flat")
        move = (f"up {abs(wow)} pts week-over-week" if wd == "up"
                else f"down {abs(wow)} pts week-over-week" if wd == "down"
                else "flat week-over-week")
        bullets.append({
            "kind": "stress",
            "text": (f"Global Ocean Freight Stress is **{stress['index']}/100** "
                     f"(**{stress['label']}**), {move}. "
                     f"{stress['chokepoints_disrupted']} of {stress['chokepoints_total']} "
                     f"monitored chokepoints are disrupted."),
            "cites": ["stress.json"],
        })

    # 2) dominant driver (top stress contributor, falls back to top-severity flag)
    top = (stress.get("contributors") or [None])[0]
    if top:
        flag = next((f for f in active if f.get("portid") == top["portid"]), None)
        extra = ""
        if flag and flag.get("kind") == "chokepoint_persistent_collapse":
            extra = " — a sustained level shift, not a fresh blip"
        bullets.append({
            "kind": "driver",
            "text": (f"The biggest driver is **{top['name']}**, running **{top['now']}/day** "
                     f"vs a normal of **{top['normal']}/day** ({top['pct_vs_normal']:+.0f}%)"
                     f"{extra}."),
            "cites": ["stress.json", "flags.json"],
            "portid": top["portid"],
        })

    # 3) this-week activity (new detections + ledger diff)
    new_week = sorted(
        [f for f in active if _within_week(f.get("as_of", ""), today)],
        key=lambda f: f.get("as_of", ""), reverse=True)
    if new_week:
        latest = new_week[0]
        names = ", ".join(f["entity"] for f in new_week[:3])
        bullets.append({
            "kind": "week",
            "text": (f"**{len(new_week)}** disruption{'s' if len(new_week) != 1 else ''} "
                     f"flagged in the last 7 days ({names}); the most recent is "
                     f"**{latest['entity']}** on {latest['as_of']}."),
            "cites": ["flags.json"],
        })
    elif events.get("events"):
        nb = events.get("new_this_run", 0)
        if events.get("baseline_run"):
            bullets.append({
                "kind": "week",
                "text": (f"Tracking **{len(active)}** active disruptions "
                         f"(timeline baseline established this run)."),
                "cites": ["events.json"],
            })
        elif nb:
            bullets.append({
                "kind": "week",
                "text": f"**{nb}** change{'s' if nb != 1 else ''} to the disruption set since the last update.",
                "cites": ["events.json"],
            })

    # 4) notable CURRENT movers beyond the lead driver — sourced from the stress
    # index's live contributors (not frozen flag pct_change, which can be stale: a
    # flag detected on a spike day may have since reverted). Keeps the brief and the
    # index from ever disagreeing.
    contribs = stress.get("contributors") or []
    lead_pid = top["portid"] if top else None
    others = [c for c in contribs if c["portid"] != lead_pid and c.get("pct_vs_normal") is not None]
    if others:
        surge = max(others, key=lambda c: c["pct_vs_normal"])
        collapse = min(others, key=lambda c: c["pct_vs_normal"])
        parts = []
        if collapse["pct_vs_normal"] < -25:
            parts.append(f"**{collapse['name']}** is running **{abs(collapse['pct_vs_normal']):.0f}% below** normal")
        if surge["pct_vs_normal"] > 35 and surge["portid"] != collapse["portid"]:
            parts.append(f"**{surge['name']}** is **{surge['pct_vs_normal']:.0f}% above** normal (a diversion/reroute signal)")
        if parts:
            bullets.append({
                "kind": "movers",
                "text": "Also moving now: " + " and ".join(parts) + ".",
                "cites": ["stress.json"],
            })

    # 5) market context (only if a flag actually links an instrument)
    inds = market.get("indicators") or {}
    if market.get("items") and inds.get("brent", {}).get("value") is not None:
        b = inds["brent"]
        bullets.append({
            "kind": "market",
            "text": (f"Market context: Brent crude **${b['value']}/bbl** "
                     f"({b['change_pct']:+}% {b['change_basis']}) — context for the "
                     f"energy-route chokepoints, not a stated cause."),
            "cites": ["market.json"],
        })

    # 6) exposure (only if a trade dataset is loaded)
    if exposure.get("exposed_value_usd"):
        cc = exposure.get("carrying_cost_of_delay_usd", {})
        bullets.append({
            "kind": "exposure",
            "text": (f"Against the loaded sample trade book, **{_money(exposure['exposed_value_usd'])}** "
                     f"routes through disrupted lanes — an estimated **{_money(cc.get('expected'))}** "
                     f"cost-of-delay ({_money(cc.get('low'))}–{_money(cc.get('high'))})."),
            "cites": ["exposure.json"],
            "note": "sample trade data — swap in your own",
        })

    as_of = stress.get("as_of") or (flags[0]["as_of"] if flags else today.isoformat())
    headline = "Ocean freight: "
    if stress.get("available"):
        headline += f"stress {stress['index']}/100 ({stress['label']})"
    else:
        headline += f"{len(active)} active disruptions"

    return {
        "generated_at": today.isoformat(),
        "as_of": as_of,
        "headline": headline,
        "stress_index": stress.get("index"),
        "stress_label": stress.get("label"),
        "active_count": len(active),
        "new_this_week": len(new_week),
        "bullets": bullets,
        "source": "IMF PortWatch (+ Stooq market context) — all figures computed from source, none generated by a model.",
    }


def run(ctx) -> dict:
    out = Path(ctx.out_dir)
    today = date.fromisoformat(ctx.today) if ctx.today else date.today()
    payload = build(out, today)
    (out / "brief.json").write_text(json.dumps(payload, separators=(",", ":")))
    return {"name": "brief", "sidecar": "brief.json", "bullets": len(payload["bullets"])}


if __name__ == "__main__":
    from ..config import publish_dir
    print(json.dumps(build(publish_dir(), date.today()), indent=2))
