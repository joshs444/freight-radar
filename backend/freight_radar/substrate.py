"""The substrate's thin unifying index — `dim_entity` + `fct_observation` (P2).

Per the critic's load-bearing correction (STANDPOINT-VISION.md §10): `fct_observation` is a
THIN unifying *index*, not a giant schema. The per-layer sidecars stay the payload; this is
the join glue that makes the whole store queryable as one tier-stamped, lineage-complete
thing. It is *narrow* (few columns, long), never *wide* (no denormalized mega-row).

`dim_entity` is the crosswalk — a stable `entity_key` for any thing a number can be about,
plus the source-native ids that resolve to it. It ships behind a **correctness gate** (known
joins AND known non-joins), because a silent mis-join mis-attributes a number — the exact
place the honesty brand quietly dies. Today IMF PortWatch is the anchor source; other
sources (LOCODE / FIPS / H3) crosswalk *into* the same `entity_key` as the spine widens.

Built server-side over the DuckDB store. **Additive**: it only CREATEs new tables and never
touches the fact tables or sidecars it reads — the published numbers are unchanged.
"""

from __future__ import annotations

from pathlib import Path

import duckdb

ENTITY_PREFIX = "pw"  # the anchor source (IMF PortWatch); others crosswalk in by LOCODE/etc.


def build_dim_entity(con: duckdb.DuckDBPyConnection) -> None:
    """One stable `entity_key` per real-world entity, with its crosswalk columns."""
    con.execute(
        f"""
        CREATE OR REPLACE TABLE dim_entity AS
        WITH u AS (
            SELECT portid, coalesce(fullname, portname) AS name, country, iso3, locode,
                   lat, lon, true AS is_chokepoint FROM dim_chokepoint
            UNION ALL
            SELECT portid, coalesce(fullname, portname), country, iso3, locode,
                   lat, lon, false FROM dim_port
        )
        SELECT '{ENTITY_PREFIX}:' || portid AS entity_key,
               CASE WHEN bool_or(is_chokepoint) THEN 'chokepoint' ELSE 'port' END AS entity_type,
               any_value(name)               AS name,
               any_value(country)            AS country,
               any_value(iso3)               AS iso3,
               nullif(any_value(locode), '') AS locode,
               any_value(lat)                AS lat,
               any_value(lon)                AS lon,
               portid                        AS source_native_id,
               'IMF PortWatch'               AS source
        FROM u
        GROUP BY portid
        """
    )


def build_fct_observation(con: duckdb.DuckDBPyConnection, knowledge_time: str, run_id: str) -> None:
    """The thin long index: one measured value per entity per day, tier + lineage stamped.

    Two measured shapes collapse onto one narrow table — the chokepoint throughput history
    and the port port-call history — proving the unification without a wide schema. Each row
    carries valid-time (`date_key` / `source_observed_at`) and knowledge-time, the bitemporal
    keystone (§4). `value` is the cited observation; tier is SPINE (we own the chain).
    """
    con.execute(
        f"""
        CREATE OR REPLACE TABLE fct_observation AS
        SELECT '{ENTITY_PREFIX}:' || portid AS entity_key,
               date                          AS date_key,
               'day'                         AS grain,
               'throughput_transits'         AS metric_key,
               'chokepoints'                 AS layer_key,
               CAST(n_total AS DOUBLE)        AS value,
               'SPINE'                       AS tier,
               'observed vessel transits (IMF PortWatch)' AS method,
               date                          AS source_observed_at,
               CAST('{knowledge_time}' AS TIMESTAMP) AS knowledge_time,
               '{run_id}'                    AS lineage_run_id
        FROM fct_chokepoint_daily
        UNION ALL
        SELECT '{ENTITY_PREFIX}:' || portid, date, 'day',
               'portcalls_total', 'ports', CAST(portcalls_total AS DOUBLE), 'SPINE',
               'observed port calls (IMF PortWatch)', date,
               CAST('{knowledge_time}' AS TIMESTAMP), '{run_id}'
        FROM fct_port_daily
        """
    )


def build_substrate(
    con: duckdb.DuckDBPyConnection,
    knowledge_time: str = "2026-01-01T00:00:00",
    run_id: str = "substrate",
) -> dict:
    build_dim_entity(con)
    build_fct_observation(con, knowledge_time=knowledge_time, run_id=run_id)
    return {
        "entities": con.execute("SELECT count(*) FROM dim_entity").fetchone()[0],
        "observations": con.execute("SELECT count(*) FROM fct_observation").fetchone()[0],
    }


def export_observation(con: duckdb.DuckDBPyConnection, out_dir) -> Path:
    """Materialize fct_observation as a compact zstd Parquet sidecar (~1.4MB for the full
    439k-row thin index) under <out_dir>/store/. Parquet (not JSON) keeps it ~30x smaller and
    is read natively by DuckDB(-WASM) — the agent-legible store, queryable in-browser at scale.
    """
    store = Path(out_dir) / "store"
    store.mkdir(parents=True, exist_ok=True)
    pth = store / "fct_observation.parquet"
    con.execute(
        f"COPY fct_observation TO '{pth}' (FORMAT parquet, COMPRESSION zstd)"  # noqa: S608 — internal path
    )
    return pth


def publish_substrate(db_path, out_dir, knowledge_time: str, run_id: str = "substrate") -> dict:
    """Build the substrate against the published DB and export the thin index to a sidecar.

    ``knowledge_time`` is the run's real as-of (NOT a static literal) — the bitemporal stamp on
    every row: 'as of when did we know this'. Called from publish; additive (only CREATEs the
    index tables, never touches the facts it reads)."""
    con = duckdb.connect(str(db_path), read_only=False)
    try:
        summary = build_substrate(con, knowledge_time=knowledge_time, run_id=run_id)
        summary["parquet"] = str(export_observation(con, out_dir))
    finally:
        con.close()
    return summary


def resolve_locode(con: duckdb.DuckDBPyConnection, locode: str) -> str | None:
    """Crosswalk a UN/LOCODE (from another source) to the one `entity_key`, or None.

    Returning None for an unknown LOCODE is the *non-join* guarantee: a second source whose
    id we don't recognize is never silently merged into an unrelated entity.
    """
    row = con.execute("SELECT entity_key FROM dim_entity WHERE locode = ?", [locode]).fetchone()
    return row[0] if row else None


def main() -> None:
    from .config import db_path

    con = duckdb.connect(str(db_path()))
    try:
        summary = build_substrate(con)
    finally:
        con.close()
    print(f"substrate built: {summary['entities']} entities, {summary['observations']} observations")


if __name__ == "__main__":
    main()
