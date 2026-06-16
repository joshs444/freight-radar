"""Tests for B2 (coverage-aware routing) + B3 (cost-of-disruption stack) + H1-B
(cape_reroute exposure via structured chokepoint refs).

The credibility properties under test:
  - a real CSV (LOCODEs, no region column) resolves instead of silently zeroing;
  - the cost stack's total is exactly carrying + reroute (no fabricated lines),
    working capital is excluded from the P&L total (locked ≠ lost), and a port
    drop carries no reroute premium (you can't reroute a port);
  - coverage is reported honestly (X of N lanes modeled);
  - the signature cape_reroute flag actually exposes Suez-routed lanes (its story
    entity matches no route — the structured `chokepoints` refs do), with the
    Cape's 10-day diversion delay and a nonzero reroute premium.
"""

from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from freight_radar.business.port_resolver import PortResolver, derive_region
from freight_radar.business import exposure as X
from freight_radar.detect.cape_reroute import CAPE_CHOKEPOINTS, detect_cape_reroute
from freight_radar.detect.detectors import DetectionConfig
from freight_radar.detect.run_detection import _write_json


def _con():
    con = duckdb.connect(":memory:")
    con.execute(
        "CREATE TABLE dim_port (portid VARCHAR, portname VARCHAR, fullname VARCHAR, "
        "iso3 VARCHAR, continent VARCHAR, lat DOUBLE, lon DOUBLE, locode VARCHAR)"
    )
    con.executemany(
        "INSERT INTO dim_port VALUES (?,?,?,?,?,?,?,?)",
        [
            ("port1", "Shanghai (Pudong)", "Shanghai", "CHN", "Asia & Pacific", 31.2, 121.5, "CN SGH"),
            ("port2", "Rotterdam", "Rotterdam", "NLD", "Europe", 51.9, 4.1, "NL RTM"),
            ("port3", "Jebel Ali", "Jebel Ali", "ARE", "Asia & Pacific", 25.0, 55.1, "AE JEA"),
        ],
    )
    return con


# --- B2: resolver + geo-derived regions ------------------------------------
def test_resolver_matches_locode_name_portid():
    r = PortResolver(_con())
    assert r.resolve("NLRTM")[0]["portid"] == "port2"     # no-space LOCODE
    assert r.resolve("NL RTM")[0]["portid"] == "port2"    # spaced LOCODE
    assert r.resolve("rotterdam")[0]["portid"] == "port2"  # name, case-insensitive
    assert r.resolve("port1")[1] == "portid"
    assert r.resolve("Nowhere-on-Sea") == (None, None)


def test_derive_region_from_geo():
    assert derive_region("Asia & Pacific", 31.2, 121.5) == "East Asia"
    assert derive_region("Europe", 51.9, 4.1) == "North Europe"
    assert derive_region("Asia & Pacific", 25.0, 55.1) == "Gulf"


def test_regionless_locode_csv_does_not_zero():
    r = PortResolver(_con())
    lane = {"origin_port": "CNSGH", "dest_port": "NLRTM", "origin_region": "", "dest_region": ""}
    cps, detail = X.route_lane(lane, r)
    assert "Suez Canal" in cps                # Asia→Europe corridor recovered
    assert detail["routing_confidence"] == "medium"   # regions were derived
    assert detail["matched_by"] == ["locode", "locode"]


# --- B3: cost-of-disruption stack ------------------------------------------
def _flag(kind, entity, portid):
    return {"kind": kind, "entity": entity, "portid": portid, "severity": 60, "lifecycle": "ongoing"}


def test_total_is_carrying_plus_reroute_only():
    flag = _flag("chokepoint_persistent_collapse", "Strait of Hormuz", "cp6")
    flows = [{"lane_id": "L1", "origin_region": "Gulf", "dest_region": "North Europe",
              "origin_port": "Jebel Ali", "dest_port": "Rotterdam", "item_category": "Chem",
              "annual_value_usd": 41_000_000.0, "annual_teu": 1000.0}]
    X.prepare_routes(flows, None)
    cs = X._business_for_flag(flag, flows)["cost_stack"]
    for k in ("low", "expected", "high"):
        assert cs["total_cost_of_disruption_usd"][k] == (
            cs["carrying_cost_of_delay_usd"][k] + cs["reroute_premium_usd"][k])
    assert cs["reroute_premium_usd"]["expected"] > 0            # Hormuz is reroutable
    # working capital is separate and NOT folded into the P&L total
    assert cs["working_capital_tied_up_usd"]["expected"] > cs["total_cost_of_disruption_usd"]["expected"]


def test_port_drop_has_no_reroute_premium():
    flag = _flag("port_activity_drop", "Shanghai (Pudong)", "port1")
    flows = [{"lane_id": "L1", "origin_region": "East Asia", "dest_region": "North Europe",
              "origin_port": "Shanghai (Pudong)", "dest_port": "Rotterdam", "item_category": "X",
              "annual_value_usd": 10_000_000.0, "annual_teu": 500.0}]
    X.prepare_routes(flows, None)
    cs = X._business_for_flag(flag, flows)["cost_stack"]
    assert cs["reroute_premium_usd"]["expected"] == 0


def test_coverage_counts_only_routed_lanes():
    flags = [_flag("chokepoint_persistent_collapse", "Suez Canal", "cp1")]
    flows = [
        {"lane_id": "L1", "origin_region": "East Asia", "dest_region": "North Europe",
         "origin_port": "Shanghai (Pudong)", "dest_port": "Rotterdam", "item_category": "X",
         "annual_value_usd": 1_000_000.0, "annual_teu": 100.0},
        {"lane_id": "L2", "origin_region": "East Asia", "dest_region": "East Asia",  # intra-basin → no corridor
         "origin_port": "Shanghai (Pudong)", "dest_port": "Ningbo", "item_category": "X",
         "annual_value_usd": 1_000_000.0, "annual_teu": 100.0},
    ]
    summary = X.enrich(flags, flows, resolver=None)
    assert summary["lanes_with_known_route"] == 1
    assert summary["total_flows"] == 2
    assert summary["coverage_pct"] == 50.0


# --- H1-B: cape_reroute flags expose Suez-routed lanes ----------------------
def _emitted_cape_flag(tmp_path) -> dict:
    """A cape flag built EXACTLY the way the pipeline emits it: the detector fires
    on a real divergence, run_detection._write_json publishes it, and exposure
    consumes the JSON dict back — the full contract, not a hand-built fixture."""
    cfg = DetectionConfig()
    w = cfg.cape_window
    idx = pd.date_range("2026-01-01", periods=2 * w, freq="D")
    red_sea = pd.Series(np.r_[np.full(w, 60.0), np.full(w, 30.0)], index=idx)  # -50%
    cape = pd.Series(np.r_[np.full(w, 90.0), np.full(w, 120.0)], index=idx)   # +33%
    flag = detect_cape_reroute(red_sea=red_sea, cape=cape, cape_lat=-34.93,
                               cape_lon=20.88, as_of=idx[-1].date(), cfg=cfg)
    assert flag is not None, "the divergence fixture must fire the detector"
    path = tmp_path / "flags.json"
    _write_json([flag], path)
    return json.loads(path.read_text())[0]


def test_cape_reroute_flag_exposes_suez_routed_lanes(tmp_path):
    """Regression for the $0-exposure bug: the cape flag's entity ('Red Sea → Cape
    of Good Hope reroute') matches no lane's route, so exposure must consume the
    structured `chokepoints` refs — and key delay/premium off the Cape entry."""
    flag = _emitted_cape_flag(tmp_path)
    assert flag["chokepoints"] == list(CAPE_CHOKEPOINTS)  # carried through flags.json

    flows = [
        {"lane_id": "L1", "origin_region": "East Asia", "dest_region": "North Europe",
         "origin_port": "Shanghai (Pudong)", "dest_port": "Rotterdam", "item_category": "X",
         "annual_value_usd": 20_000_000.0, "annual_teu": 1_500.0},  # routes via Suez + Bab
        {"lane_id": "L2", "origin_region": "East Asia", "dest_region": "North America West",
         "origin_port": "Shanghai (Pudong)", "dest_port": "Los Angeles", "item_category": "X",
         "annual_value_usd": 9_000_000.0, "annual_teu": 800.0},     # no Red Sea leg
    ]
    X.prepare_routes(flows, None)
    b = X._business_for_flag(flag, flows)
    assert b["lane_count"] == 1                                     # was 0 before H1-B
    assert b["exposed_lanes"][0]["lane_id"] == "L1"
    # Cape diversion delay (10d), NOT the 3d unknown-chokepoint default
    assert b["est_delay_days"]["expected"] == X.REROUTE_DELAY["Cape of Good Hope"]
    # the premium calibrated for exactly this case is no longer zero
    assert b["cost_stack"]["reroute_premium_usd"]["expected"] > 0
    assert b["total_cost_of_disruption_usd"]["expected"] > 0
    # and the portfolio summary counts it as an active disruption hitting you
    summary = X.enrich([flag], flows, resolver=None)
    assert summary["active_disruptions_hitting_you"] == 1
    assert summary["exposed_value_usd"] == 20_000_000


def test_cape_flag_without_chokepoints_degrades_to_entity_match():
    """Back-compat: an old flags.json row with no `chokepoints` falls back to entity
    matching (zero lanes — the entity is a story string), but delay/premium still
    key off the Cape entry by kind, never the unknown-chokepoint default."""
    flag = _flag("cape_reroute", "Red Sea → Cape of Good Hope reroute", "chokepoint7")
    flows = [{"lane_id": "L1", "origin_region": "East Asia", "dest_region": "North Europe",
              "origin_port": "Shanghai (Pudong)", "dest_port": "Rotterdam", "item_category": "X",
              "annual_value_usd": 5_000_000.0, "annual_teu": 400.0}]
    X.prepare_routes(flows, None)
    b = X._business_for_flag(flag, flows)
    assert b["lane_count"] == 0  # documented fallback — no structured refs, no match
    assert b["est_delay_days"]["expected"] == X.REROUTE_DELAY["Cape of Good Hope"]
