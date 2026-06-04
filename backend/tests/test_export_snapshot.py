"""Snapshot exporter tests — the per-entity cargo-mix block (Phase A1).

Builds a tiny in-memory DuckDB with the exact columns the snapshot queries read,
then asserts every record carries a ``cargo_mix`` whose 5 leaf vessel types sum
*exactly* to the headline total (PortWatch's invariant:
container+tanker+dry_bulk+general_cargo+roro == *_total). No network, no real DB.
"""

from __future__ import annotations

import duckdb

from freight_radar import export_snapshot as ES


def _con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(
        """
        CREATE TABLE dim_chokepoint(
            portid VARCHAR, fullname VARCHAR, country VARCHAR, lat DOUBLE, lon DOUBLE,
            industry_top1 VARCHAR, vessel_count_total BIGINT);
        CREATE TABLE fct_chokepoint_daily(
            portid VARCHAR, date DATE, n_total BIGINT, n_container BIGINT, n_tanker BIGINT,
            n_dry_bulk BIGINT, n_general_cargo BIGINT, n_roro BIGINT, capacity_total BIGINT);
        CREATE TABLE dim_port(
            portid VARCHAR, portname VARCHAR, country VARCHAR, lat DOUBLE, lon DOUBLE,
            vessel_count_total BIGINT);
        CREATE TABLE fct_port_daily(
            portid VARCHAR, date DATE, portcalls_total BIGINT, portcalls_container BIGINT,
            portcalls_tanker BIGINT, portcalls_dry_bulk BIGINT,
            portcalls_general_cargo BIGINT, portcalls_roro BIGINT);
        """
    )
    con.execute(
        """
        INSERT INTO dim_chokepoint VALUES
          ('chokepoint1','Suez Canal','Egypt',30.0,32.5,'Energy',900),
          ('chokepoint9','Empty Strait','Nowhere',0.0,0.0,'n/a',1);
        -- a prior day + the latest day so arg_max(date) resolves to the latest
        INSERT INTO fct_chokepoint_daily VALUES
          ('chokepoint1','2026-05-30', 20, 9,5,3,2,1, 1000000),
          ('chokepoint1','2026-05-31', 21,10,5,3,2,1, 1100000),
          ('chokepoint9','2026-05-31',  0, 0,0,0,0,0,       0);
        INSERT INTO dim_port VALUES
          ('port1','Shanghai','China',31.2,121.5, 5000),
          ('port2','Ghost Port','Nowhere',1.0,1.0, 2);
        INSERT INTO fct_port_daily VALUES
          ('port1','2026-05-29', 120, 38,73,1,5,3),
          ('port2','2026-05-29',   0,  0, 0,0,0,0);
        """
    )
    return con


def test_chokepoint_cargo_mix_sums_to_total():
    con = _con()
    recs = {c["portid"]: c for c in ES._chokepoints(con)}
    suez = recs["chokepoint1"]
    mix = suez["cargo_mix"]
    assert set(mix) == set(ES.CARGO_TYPES)
    assert sum(mix.values()) == suez["n_total"] == 21
    assert mix == {"container": 10, "tanker": 5, "dry_bulk": 3, "general_cargo": 2, "roro": 1}


def test_port_cargo_mix_sums_to_portcalls():
    con = _con()
    recs = {p["portid"]: p for p in ES._ports(con)}
    shanghai = recs["port1"]
    mix = shanghai["cargo_mix"]
    assert set(mix) == set(ES.CARGO_TYPES)
    assert sum(mix.values()) == shanghai["portcalls"] == 120


def test_empty_breakdown_yields_none():
    """A row with no vessels of any type carries cargo_mix=None (frontend skips it)."""
    con = _con()
    choke = {c["portid"]: c for c in ES._chokepoints(con)}
    port = {p["portid"]: p for p in ES._ports(con)}
    assert choke["chokepoint9"]["cargo_mix"] is None
    assert port["port2"]["cargo_mix"] is None
