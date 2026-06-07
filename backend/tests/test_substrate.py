"""P2 — the substrate's thin unifying index + the crosswalk CORRECTNESS gate.

dim_entity must give one stable entity_key per entity (a bijection with the source id),
resolve known cross-source joins, and — the load-bearing half — keep known non-joins
*separate* (a silent mis-join mis-attributes a number). fct_observation must be a thin,
tier-stamped, valid-time-correct long index over the existing facts, and purely additive
(it never mutates the fact tables it reads).
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import duckdb
import pytest

from freight_radar.substrate import build_substrate, resolve_locode

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_BUILDER = REPO_ROOT / "dbt" / "ci" / "build_fixture_db.py"


@pytest.fixture(scope="module")
def con(tmp_path_factory):
    db = tmp_path_factory.mktemp("substrate") / "fixture.duckdb"
    spec = importlib.util.spec_from_file_location("_fx", FIXTURE_BUILDER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    os.environ["FREIGHT_RADAR_DB"] = str(db)
    mod.main()
    c = duckdb.connect(str(db))
    build_substrate(c, knowledge_time="2026-06-01T00:00:00", run_id="test")
    yield c
    c.close()


def test_dim_entity_is_a_bijection_with_source_ids(con) -> None:
    n_entities, n_ids, n_keys = con.execute(
        "SELECT count(*), count(DISTINCT source_native_id), count(DISTINCT entity_key) FROM dim_entity"
    ).fetchone()
    assert n_entities == n_ids == n_keys, "entity_key must be 1:1 with the source id (no dup, no merge)"
    # the fixture has 28 chokepoints + 46 ports, disjoint
    assert n_entities == 74
    assert con.execute("SELECT count(*) FROM dim_entity WHERE entity_type='chokepoint'").fetchone()[0] == 28


def test_crosswalk_resolves_known_joins(con) -> None:
    # a LOCODE from a second source must resolve to the right PortWatch entity
    assert resolve_locode(con, "NL RTM") == "pw:port1114"  # Rotterdam
    assert resolve_locode(con, "KR PUS") == "pw:port1065"  # Busan


def test_crosswalk_keeps_known_non_joins_separate(con) -> None:
    # distinct ports never collapse into one entity_key
    busan = resolve_locode(con, "KR PUS")
    qingdao = resolve_locode(con, "CN QDG")
    assert busan is not None and qingdao is not None and busan != qingdao
    # an unknown LOCODE is NEVER silently merged into some entity
    assert resolve_locode(con, "ZZ ZZZ") is None
    assert resolve_locode(con, "") is None


def test_fct_observation_is_thin_tier_stamped_and_valid_time_correct(con) -> None:
    cols = [r[0] for r in con.execute("DESCRIBE fct_observation").fetchall()]
    # thin = a narrow long index, not a wide schema
    assert len(cols) <= 12, f"fct_observation got wide ({len(cols)} cols) — keep it a thin index"
    assert {"entity_key", "date_key", "metric_key", "value", "tier", "source_observed_at"} <= set(cols)
    # every row tier-stamped + valid-time == the observation date (the bitemporal keystone)
    assert con.execute("SELECT count(*) FROM fct_observation WHERE tier <> 'SPINE'").fetchone()[0] == 0
    assert con.execute(
        "SELECT count(*) FROM fct_observation WHERE source_observed_at <> date_key"
    ).fetchone()[0] == 0
    # both measured shapes unified onto the one table
    metrics = {r[0] for r in con.execute("SELECT DISTINCT metric_key FROM fct_observation").fetchall()}
    assert metrics == {"throughput_transits", "portcalls_total"}


def test_every_observation_resolves_to_an_entity(con) -> None:
    orphans = con.execute(
        "SELECT count(*) FROM fct_observation o "
        "LEFT JOIN dim_entity e USING (entity_key) WHERE e.entity_key IS NULL"
    ).fetchone()[0]
    assert orphans == 0, "every observation must resolve to a dim_entity (no dangling number)"


def test_value_matches_the_source_fact(con) -> None:
    # a spot-check that the index didn't transform the number — it indexes, it doesn't recompute
    src = con.execute(
        "SELECT n_total FROM fct_chokepoint_daily WHERE portid='chokepoint1' ORDER BY date DESC LIMIT 1"
    ).fetchone()[0]
    idx = con.execute(
        "SELECT value FROM fct_observation WHERE entity_key='pw:chokepoint1' "
        "AND metric_key='throughput_transits' ORDER BY date_key DESC LIMIT 1"
    ).fetchone()[0]
    assert float(idx) == float(src)


def test_knowledge_time_is_the_passed_run_value_not_a_static_literal(con) -> None:
    # the bitemporal stamp must be THIS run's knowledge_time (the fixture passes 2026-06-01),
    # never a hardcoded "2026-01-01" literal — else time-travel is a lie.
    kts = {r[0] for r in con.execute("SELECT DISTINCT knowledge_time FROM fct_observation").fetchall()}
    assert len(kts) == 1
    assert str(next(iter(kts))).startswith("2026-06-01"), kts


def test_export_observation_writes_a_readable_parquet(con, tmp_path) -> None:
    import duckdb

    from freight_radar.substrate import export_observation

    pth = export_observation(con, tmp_path)
    assert pth.exists() and pth.suffix == ".parquet"
    # the Parquet round-trips: same row count + bitemporal columns intact
    n_src = con.execute("SELECT count(*) FROM fct_observation").fetchone()[0]
    rc = duckdb.connect()
    try:
        n_pq, cols = rc.execute(f"SELECT count(*) FROM read_parquet('{pth}')").fetchone()[0], [
            r[0] for r in rc.execute(f"DESCRIBE SELECT * FROM read_parquet('{pth}')").fetchall()
        ]
    finally:
        rc.close()
    assert n_pq == n_src and n_pq > 0
    assert {"entity_key", "date_key", "value", "knowledge_time", "lineage_run_id"} <= set(cols)


def test_build_is_additive(con) -> None:
    # building the substrate must not mutate the fact tables it reads
    n = con.execute("SELECT count(*) FROM fct_chokepoint_daily").fetchone()[0]
    build_substrate(con, knowledge_time="2026-06-02T00:00:00", run_id="rerun")  # idempotent rebuild
    assert con.execute("SELECT count(*) FROM fct_chokepoint_daily").fetchone()[0] == n
