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


def route_chokepoints(lane: dict) -> set[str]:
    cps: set[str] = set()
    for region in (lane["origin_region"], lane["dest_region"]):
        cps.update(GATEWAY.get(region, []))
    for port in (lane["origin_port"], lane["dest_port"]):
        cps.update(PORT_CHOKEPOINTS.get(port, []))
    cps.update(CORRIDOR.get(frozenset({lane["origin_region"], lane["dest_region"]}), []))
    return cps


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
    entity = flag["entity"]
    if _is_chokepoint(flag):
        return [ln for ln in flows if entity in route_chokepoints(ln)]
    return [ln for ln in flows if entity in (ln["origin_port"], ln["dest_port"])]


def _delay_days(flag: dict) -> int:
    if _is_chokepoint(flag):
        return REROUTE_DELAY.get(flag["entity"], DEFAULT_CHOKE_DELAY)
    # port congestion/drop: scale modestly with severity
    return max(2, round(flag.get("severity", 30) / 12))


def _business_for_flag(flag: dict, flows: list[dict]) -> dict:
    lanes = _exposed_lanes(flag, flows)
    value = sum(ln["annual_value_usd"] for ln in lanes)
    teu = sum(ln["annual_teu"] for ln in lanes)
    delay = _delay_days(flag)
    by_item: dict[str, float] = defaultdict(float)
    for ln in lanes:
        by_item[ln["item_category"]] += ln["annual_value_usd"]
    top_items = [k for k, _ in sorted(by_item.items(), key=lambda kv: kv[1], reverse=True)[:3]]
    return {
        "exposed_value_usd": round(value),
        "exposed_teu": round(teu),
        "exposed_lanes": [
            {"lane_id": ln["lane_id"], "from": ln["origin_port"], "to": ln["dest_port"],
             "item": ln["item_category"], "value_usd": round(ln["annual_value_usd"])}
            for ln in sorted(lanes, key=lambda x: x["annual_value_usd"], reverse=True)
        ],
        "lane_count": len(lanes),
        "top_items": top_items,
        "est_delay_days": delay,
        # value of goods delayed ≈ annual value prorated over the delay window
        "value_at_risk_usd": round(value * delay / 365),
    }


def enrich(flags: list[dict], flows: list[dict]) -> dict:
    """Attach `business` to each flag; return a portfolio exposure summary."""
    active = [f for f in flags if f.get("lifecycle") != "resolved"]
    exposed_lane_ids: set[str] = set()
    total_var = 0
    disrupted = 0
    for f in flags:
        f["business"] = _business_for_flag(f, flows)
    for f in active:
        b = f["business"]
        if b["lane_count"]:
            disrupted += 1
            total_var += b["value_at_risk_usd"]
            exposed_lane_ids.update(ln["lane_id"] for ln in b["exposed_lanes"])

    total_value = sum(ln["annual_value_usd"] for ln in flows)
    exposed_value = sum(
        ln["annual_value_usd"] for ln in flows if ln["lane_id"] in exposed_lane_ids
    )
    return {
        "total_flows": len(flows),
        "total_value_usd": round(total_value),
        "exposed_lanes": len(exposed_lane_ids),
        "exposed_value_usd": round(exposed_value),
        "value_at_risk_usd": round(total_var),
        "active_disruptions_hitting_you": disrupted,
    }


def enrich_from_files(flags_path: Path = None, flows_path: Path = None, out_dir: Path = None) -> dict:
    out = out_dir or publish_dir()
    flags_path = flags_path or (out / "flags.json")
    flows_path = Path(os.environ.get("FREIGHT_RADAR_FLOWS", str(flows_path or DEFAULT_FLOWS)))

    flags = json.loads(Path(flags_path).read_text())
    flows = load_flows(flows_path)
    summary = enrich(flags, flows)

    Path(flags_path).write_text(json.dumps(flags, indent=2))
    (out / "exposure.json").write_text(json.dumps(summary, indent=2))
    return summary


if __name__ == "__main__":
    print(json.dumps(enrich_from_files(), indent=2))
