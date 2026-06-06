"""Append-only event ledger — the "what happened" spine the brief cites.

Each tick we fingerprint the current flags and diff them against the persisted
state from the previous tick, emitting three kinds of events:

  appeared   — a flag_id we'd never seen (a new disruption detected)
  escalated  — a flag we'd seen whose severity rose by >= ESCALATE_BY
  resolved   — a flag_id present last tick but gone now (disruption cleared)

The diff state lives in ``data/state/events_state.json`` and the rolling ledger in
``events.json`` (capped). Both are committed, so the timeline survives across runs
and deploys and the week-over-week brief has real history to reference. On the very
first run there is no prior state, so every active flag fairly registers as
"appeared" (an honest baseline, not a fabricated week of activity).

Events are stamped with the data's own as_of date (deterministic — no wall clock),
plus a monotonic sequence so order is stable within a day.
"""

from __future__ import annotations

import json
from pathlib import Path

ESCALATE_BY = 10      # severity points
LEDGER_CAP = 120      # keep the most recent N events in events.json
STATE_DIR = "state"   # under data/  (sibling of the duckdb)


def _state_path(ctx) -> Path:
    # ctx.db_path is .../data/freight_radar.duckdb -> .../data/state/events_state.json
    data_dir = Path(ctx.db_path).parent
    d = data_dir / STATE_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d / "events_state.json"


def _fingerprint(flags: list[dict]) -> dict:
    out = {}
    for f in flags:
        if f.get("lifecycle") == "resolved":
            continue
        out[f["flag_id"]] = {
            "entity": f.get("entity"),
            "kind": f.get("kind"),
            "severity": int(f.get("severity", 0)),
            "as_of": f.get("as_of"),
            "pct_change": f.get("pct_change"),
            "portid": f.get("portid"),
        }
    return out


def diff(prev: dict, curr: dict, when: str, start_seq: int) -> list[dict]:
    events: list[dict] = []
    seq = start_seq

    for fid, c in curr.items():
        if fid not in prev:
            seq += 1
            events.append({"seq": seq, "at": when, "type": "appeared", "flag_id": fid,
                           "entity": c["entity"], "kind": c["kind"], "severity": c["severity"],
                           "pct_change": c.get("pct_change"), "portid": c.get("portid")})
        else:
            rise = c["severity"] - prev[fid].get("severity", c["severity"])
            if rise >= ESCALATE_BY:
                seq += 1
                events.append({"seq": seq, "at": when, "type": "escalated", "flag_id": fid,
                               "entity": c["entity"], "kind": c["kind"], "severity": c["severity"],
                               "from_severity": prev[fid]["severity"], "portid": c.get("portid")})

    for fid, p in prev.items():
        if fid not in curr:
            seq += 1
            events.append({"seq": seq, "at": when, "type": "resolved", "flag_id": fid,
                           "entity": p["entity"], "kind": p["kind"],
                           "severity": p.get("severity"), "portid": p.get("portid")})
    return events


def run(ctx) -> dict:
    out = Path(ctx.out_dir)
    flags_path = Path(ctx.flags_path)
    if not flags_path.exists():
        return {"name": "events", "error": "flags.json missing"}
    flags = json.loads(flags_path.read_text())
    curr = _fingerprint(flags)

    state_path = _state_path(ctx)
    ledger_path = out / "events.json"
    prev_state = {}
    if state_path.exists():
        try:
            prev_state = json.loads(state_path.read_text())
        except json.JSONDecodeError:
            prev_state = {}
    prev_fp = prev_state.get("fingerprint", {})
    last_seq = int(prev_state.get("last_seq", 0))
    is_first = not prev_fp

    when = ctx.as_of or ctx.today
    new_events = diff(prev_fp, curr, when, last_seq)

    # load existing ledger, append, cap
    existing = []
    if ledger_path.exists():
        try:
            existing = json.loads(ledger_path.read_text()).get("events", [])
        except json.JSONDecodeError:
            existing = []
    # dedup by (flag_id, type, at) so a re-run — or a state-persistence hiccup that
    # re-"appears" every flag — can't inflate event_count with duplicate rows.
    seen: set = set()
    deduped = []
    for e in existing + new_events:
        k = (e.get("flag_id"), e.get("type"), e.get("at"))
        if k in seen:
            continue
        seen.add(k)
        deduped.append(e)
    ledger = deduped[-LEDGER_CAP:]
    new_last_seq = max([last_seq] + [e["seq"] for e in new_events])

    payload = {
        "generated_at": ctx.today,
        "as_of": when,
        "baseline_run": is_first,
        "event_count": len(ledger),
        "new_this_run": len(new_events),
        "events": list(reversed(ledger)),  # newest first for the UI
    }
    ledger_path.write_text(json.dumps(payload, separators=(",", ":")))
    state_path.write_text(json.dumps(
        {"fingerprint": curr, "last_seq": new_last_seq, "as_of": when},
        separators=(",", ":")))

    return {"name": "events", "sidecar": "events.json",
            "new_this_run": len(new_events), "baseline": is_first}


if __name__ == "__main__":
    import json as _j
    from ..enrich import build_ctx
    print(_j.dumps(run(build_ctx()), indent=2))
