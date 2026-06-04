"""Business-impact linking: map disruptions -> a user's trade flows -> exposure.

You provide a trade dataset (CSV: lanes with origin/destination region+port, item
category, annual value + TEU). For each active flag we find which of *your* lanes
route through that chokepoint or call that port, sum the value/volume at risk, and
estimate the added delay. The result is attached to each flag (`business`) and
summarised (`exposure.json`).

The routing model + delay figures are transparent ESTIMATES, documented below and
labelled as such in the UI — never presented as precise logistics modelling.

Swap in your own data: replace samples/business_flows.csv (same columns) or set
FREIGHT_RADAR_FLOWS to a path.
"""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from pathlib import Path

from ..config import BACKEND_DIR, publish_dir

DEFAULT_FLOWS = BACKEND_DIR / "samples" / "business_flows.csv"

# --- routing model: which chokepoints a lane's route passes ----------------
# Gateway chokepoints a region's traffic must transit to leave its basin.
GATEWAY = {
    "Black Sea": ["Bosporus Strait"],
    "Baltic": ["Oresund Strait"],
    "Gulf": ["Strait of Hormuz"],
}
# Port-specific gateways (overrides for sub-basins, e.g. Azov -> Kerch).
PORT_CHOKEPOINTS = {
    "Rostov-on-Don": ["Kerch Strait"],
}
# Long-haul corridors between region pairs (order-independent).
CORRIDOR = {
    frozenset({"East Asia", "North Europe"}): ["Malacca Strait", "Bab el-Mandeb Strait", "Suez Canal", "Gibraltar Strait", "Dover Strait"],
    frozenset({"Southeast Asia", "North Europe"}): ["Malacca Strait", "Bab el-Mandeb Strait", "Suez Canal", "Gibraltar Strait", "Dover Strait"],
    frozenset({"South Asia", "North Europe"}): ["Bab el-Mandeb Strait", "Suez Canal", "Gibraltar Strait", "Dover Strait"],
    frozenset({"East Asia", "Mediterranean"}): ["Malacca Strait", "Bab el-Mandeb Strait", "Suez Canal"],
    frozenset({"Southeast Asia", "Mediterranean"}): ["Malacca Strait", "Bab el-Mandeb Strait", "Suez Canal"],
    frozenset({"East Asia", "North America East"}): ["Panama Canal"],
    frozenset({"Southeast Asia", "North America East"}): ["Panama Canal"],
    frozenset({"East Asia", "North America West"}): ["Taiwan Strait"],
    frozenset({"Gulf", "East Asia"}): ["Malacca Strait"],
    frozenset({"Gulf", "North Europe"}): ["Bab el-Mandeb Strait", "Suez Canal", "Gibraltar Strait", "Dover Strait"],
    frozenset({"Gulf", "Mediterranean"}): ["Bab el-Mandeb Strait", "Suez Canal"],
    frozenset({"Black Sea", "North Europe"}): ["Gibraltar Strait", "Dover Strait"],
    frozenset({"Mediterranean", "North America East"}): ["Gibraltar Strait"],
}

# Estimated added transit delay (days) when a chokepoint is disrupted (reroute/wait).
REROUTE_DELAY = {
    "Suez Canal": 12, "Bab el-Mandeb Strait": 12, "Cape of Good Hope": 10,
    "Strait of Hormuz": 6, "Panama Canal": 8, "Malacca Strait": 3,
    "Bosporus Strait": 4, "Kerch Strait": 4, "Oresund Strait": 2,
    "Gibraltar Strait": 3, "Dover Strait": 2, "Taiwan Strait": 3, "Korea Strait": 2,
}
DEFAULT_CHOKE_DELAY = 3


def route_lane(lane: dict, resolver=None) -> tuple[set[str], dict]:
    """Chokepoints a lane transits, plus a routing receipt (how it resolved + a
    confidence). With a resolver, ports resolve by LOCODE/portid/name and a missing
    region is derived from geography — so a real CSV doesn't silently zero."""
    o_region = (lane.get("origin_region") or "").strip()
    d_region = (lane.get("dest_region") or "").strip()
    o_rec = d_rec = None
    o_match = d_match = None
    region_derived = False
    if resolver is not None:
        o_region2, o_rec, o_match = resolver.region_for(lane.get("origin_port", ""), o_region)
        d_region2, d_rec, d_match = resolver.region_for(lane.get("dest_port", ""), d_region)
        region_derived = bool((not o_region and o_region2) or (not d_region and d_region2))
        o_region, d_region = o_region2, d_region2

    cps: set[str] = set()
    for region in (o_region, d_region):
        cps.update(GATEWAY.get(region, []))
    for port in (lane.get("origin_port"), lane.get("dest_port")):
        cps.update(PORT_CHOKEPOINTS.get(port, []))
    cps.update(CORRIDOR.get(frozenset({o_region, d_region}), []))

    both_resolved = (o_rec is not None and d_rec is not None) if resolver is not None else True
    if cps and both_resolved and not region_derived:
        conf = "high"
    elif cps and both_resolved:
        conf = "medium"
    elif cps:
        conf = "low"
    else:
        conf = "none"

    detail = {
        "origin_portid": o_rec["portid"] if o_rec else None,
        "dest_portid": d_rec["portid"] if d_rec else None,
        "origin_region": o_region, "dest_region": d_region,
        "matched_by": [m for m in (o_match, d_match) if m],
        "routing_confidence": conf,
        "route_chokepoints": sorted(cps),
    }
    return cps, detail


def prepare_routes(flows: list[dict], resolver=None) -> None:
    """Compute each lane's route once, caching it on the lane dict."""
    for ln in flows:
        cps, detail = route_lane(ln, resolver)
        ln["_route_cps"] = cps
        ln["_routing"] = detail
        ln["_origin_portid"] = detail["origin_portid"]
        ln["_dest_portid"] = detail["dest_portid"]


def load_flows(path: Path = DEFAULT_FLOWS) -> list[dict]:
    rows = []
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            r["annual_value_usd"] = float(r.get("annual_value_usd") or 0)
            r["annual_teu"] = float(r.get("annual_teu") or 0)
            rows.append(r)
    return rows


def _is_chokepoint(flag: dict) -> bool:
    return flag.get("kind", "").startswith("chokepoint") or flag.get("kind") == "cape_reroute"


def _exposed_lanes(flag: dict, flows: list[dict]) -> list[dict]:
    """Lanes hit by a flag. Assumes prepare_routes() has run (lanes carry _route_cps).
    Port flags match a resolved portid first, then fall back to a name match."""
    entity = flag["entity"]
    if _is_chokepoint(flag):
        return [ln for ln in flows if entity in ln.get("_route_cps", set())]
    return [ln for ln in flows
            if flag["portid"] in (ln.get("_origin_portid"), ln.get("_dest_portid"))
            or entity in (ln["origin_port"], ln["dest_port"])]


# Annual inventory carrying cost (low/expected/high). The v1 number silently used
# 100%/yr (value*delay/365) — a ~4x overstatement; industry is ~20-30%/yr.
CARRYING_RATE = (0.20, 0.25, 0.30)

# Reroute premium: extra fuel + charter for taking the longer way round when a
# chokepoint forces a diversion (e.g. Suez -> Cape). Scaled per-TEU per extra
# diversion-day; ~$25/TEU/day expected lands a large containership's Cape diversion
# near the widely-cited ~$1M+/voyage. Only applied to reroutable chokepoint flags.
REROUTE_PREMIUM_PER_TEU_DAY = (15, 25, 40)


def _delay_days(flag: dict) -> int:
    if _is_chokepoint(flag):
        return REROUTE_DELAY.get(flag["entity"], DEFAULT_CHOKE_DELAY)
    # port congestion/drop: scale modestly with severity
    return max(2, round(flag.get("severity", 30) / 12))


def _delay_band(flag: dict) -> dict:
    d = _delay_days(flag)
    return {"low": max(1, round(d * 0.7)), "expected": d, "high": round(d * 1.35)}


def _carrying_band(value: float, db: dict) -> dict:
    # cost-of-delay = value × carrying_rate × delay/365 (the corrected figure)
    return {k: round(value * CARRYING_RATE[i] * db[k] / 365)
            for i, k in enumerate(("low", "expected", "high"))}


def _working_capital_band(value: float, db: dict) -> dict:
    # capital LOCKED in goods in transit longer = gross value prorated (not lost)
    return {k: round(value * db[k] / 365) for k in ("low", "expected", "high")}


def _reroute_premium_band(teu: float, flag: dict, db: dict) -> dict:
    """Extra fuel/charter from diverting around a closed chokepoint. Only reroutable
    chokepoint flags incur it; port-drop flags don't (you can't reroute a port)."""
    if not _is_chokepoint(flag) or flag["entity"] not in REROUTE_DELAY:
        return {"low": 0, "expected": 0, "high": 0}
    return {k: round(teu * REROUTE_PREMIUM_PER_TEU_DAY[i] * db[k])
            for i, k in enumerate(("low", "expected", "high"))}


def _sum_band(*bands: dict) -> dict:
    return {k: round(sum(b.get(k, 0) for b in bands)) for k in ("low", "expected", "high")}


def _best_confidence(lanes: list[dict]) -> str:
    order = {"high": 3, "medium": 2, "low": 1, "none": 0}
    best = max((ln.get("_routing", {}).get("routing_confidence", "none") for ln in lanes),
              key=lambda c: order.get(c, 0), default="none")
    return best


def _business_for_flag(flag: dict, flows: list[dict]) -> dict:
    lanes = _exposed_lanes(flag, flows)
    value = sum(ln["annual_value_usd"] for ln in lanes)
    teu = sum(ln["annual_teu"] for ln in lanes)
    delay_band = _delay_band(flag)
    by_item: dict[str, float] = defaultdict(float)
    for ln in lanes:
        by_item[ln["item_category"]] += ln["annual_value_usd"]
    top_items = [k for k, _ in sorted(by_item.items(), key=lambda kv: kv[1], reverse=True)[:3]]

    carrying = _carrying_band(value, delay_band)
    reroute = _reroute_premium_band(teu, flag, delay_band)
    working_capital = _working_capital_band(value, delay_band)
    # P&L cost of disruption = carrying + reroute. Working capital is balance-sheet
    # (locked, not lost) and is deliberately NOT summed in — no double counting.
    total = _sum_band(carrying, reroute)

    method = [
        {"line": "carrying_cost_of_delay", "basis": f"value × {int(CARRYING_RATE[1]*100)}%/yr carrying × delay/365"},
    ]
    if reroute["expected"]:
        method.append({"line": "reroute_premium",
                       "basis": f"TEU × ~${REROUTE_PREMIUM_PER_TEU_DAY[1]}/TEU/diversion-day × delay"})
    method.append({"line": "working_capital_tied_up",
                   "basis": "value × delay/365 (balance-sheet, excluded from P&L total)"})

    return {
        "exposed_value_usd": round(value),
        "exposed_teu": round(teu),
        "exposed_lanes": [
            {"lane_id": ln["lane_id"], "from": ln["origin_port"], "to": ln["dest_port"],
             "item": ln["item_category"], "value_usd": round(ln["annual_value_usd"]),
             "routing_confidence": ln.get("_routing", {}).get("routing_confidence", "none")}
            for ln in sorted(lanes, key=lambda x: x["annual_value_usd"], reverse=True)
        ],
        "lane_count": len(lanes),
        "top_items": top_items,
        "routing_confidence": _best_confidence(lanes),
        "est_delay_days": delay_band,                              # band, not a point
        "cost_stack": {                                            # B3: the banded stack
            "carrying_cost_of_delay_usd": carrying,
            "reroute_premium_usd": reroute,
            "total_cost_of_disruption_usd": total,                # carrying + reroute
            "working_capital_tied_up_usd": working_capital,       # excluded from total
        },
        "method": method,
        # back-compat top-level fields (the feed + summary still read these)
        "carrying_cost_of_delay_usd": carrying,
        "working_capital_tied_up_usd": working_capital,
        "total_cost_of_disruption_usd": total,
        "carrying_rate_assumed": CARRYING_RATE[1],
    }


def enrich(flags: list[dict], flows: list[dict], resolver=None) -> dict:
    """Attach `business` to each flag; return a portfolio exposure summary.

    With a resolver, routing is coverage-aware (LOCODE/name resolution + geo-derived
    regions) and the summary reports how many lanes were actually modeled."""
    prepare_routes(flows, resolver)
    active = [f for f in flags if f.get("lifecycle") != "resolved"]
    exposed_lane_ids: set[str] = set()
    carry = {"low": 0, "expected": 0, "high": 0}
    wc = {"low": 0, "expected": 0, "high": 0}
    total_cost = {"low": 0, "expected": 0, "high": 0}
    disrupted = 0
    for f in flags:
        f["business"] = _business_for_flag(f, flows)
    for f in active:
        b = f["business"]
        if b["lane_count"]:
            disrupted += 1
            for k in ("low", "expected", "high"):
                carry[k] += b["carrying_cost_of_delay_usd"][k]
                wc[k] += b["working_capital_tied_up_usd"][k]
                total_cost[k] += b["total_cost_of_disruption_usd"][k]
            exposed_lane_ids.update(ln["lane_id"] for ln in b["exposed_lanes"])

    total_value = sum(ln["annual_value_usd"] for ln in flows)
    exposed_value = sum(
        ln["annual_value_usd"] for ln in flows if ln["lane_id"] in exposed_lane_ids
    )
    modeled = [ln for ln in flows if ln.get("_route_cps")]
    return {
        "total_flows": len(flows),
        "total_value_usd": round(total_value),
        "exposed_lanes": len(exposed_lane_ids),
        "exposed_value_usd": round(exposed_value),
        "carrying_cost_of_delay_usd": carry,           # banded; the corrected headline
        "working_capital_tied_up_usd": wc,             # capital locked in transit (not lost)
        "total_cost_of_disruption_usd": total_cost,    # carrying + reroute (P&L)
        "carrying_rate_assumed": CARRYING_RATE[1],
        "active_disruptions_hitting_you": disrupted,
        "lanes_with_known_route": len(modeled),        # coverage — never hidden
        "coverage_pct": round(len(modeled) / len(flows) * 100, 1) if flows else 0.0,
    }


def _resolver_for(db) -> object | None:
    if db is None:
        return None
    try:
        import duckdb
        from .port_resolver import PortResolver
        con = duckdb.connect(str(db), read_only=True)
        try:
            return PortResolver(con)
        finally:
            con.close()
    except Exception:  # noqa: BLE001 — degrade to back-compat string routing
        return None


def enrich_from_files(flags_path: Path = None, flows_path: Path = None,
                      out_dir: Path = None, db=None) -> dict:
    out = out_dir or publish_dir()
    flags_path = flags_path or (out / "flags.json")
    flows_path = Path(os.environ.get("FREIGHT_RADAR_FLOWS", str(flows_path or DEFAULT_FLOWS)))

    flags = json.loads(Path(flags_path).read_text())
    flows = load_flows(flows_path)
    summary = enrich(flags, flows, resolver=_resolver_for(db))

    Path(flags_path).write_text(json.dumps(flags, indent=2))
    (out / "exposure.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    print(json.dumps(enrich_from_files(), indent=2))
