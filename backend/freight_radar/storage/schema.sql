-- Freight Radar — DuckDB schema (the single seam the app reads from).
-- All numbers in the app trace back to these tables; nothing reads upstream directly.

-- ---------------------------------------------------------------------------
-- Reference dimensions (lat/lon are WGS84 decimal degrees, straight from attrs).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS dim_chokepoint (
    portid              VARCHAR PRIMARY KEY,   -- 'chokepoint1'..'chokepoint28'
    fullname            VARCHAR,
    portname            VARCHAR,
    country             VARCHAR,
    iso3                VARCHAR,
    continent           VARCHAR,
    lat                 DOUBLE,
    lon                 DOUBLE,
    vessel_count_total          BIGINT,
    vessel_count_container      BIGINT,
    vessel_count_dry_bulk       BIGINT,
    vessel_count_general_cargo  BIGINT,
    vessel_count_roro           BIGINT,
    vessel_count_tanker         BIGINT,
    -- this entity's share of its COUNTRY's maritime trade (0-100 %), an IMF
    -- systemic-importance signal: a sole-gateway port scores near 100.
    share_country_maritime_import  DOUBLE,
    share_country_maritime_export  DOUBLE,
    industry_top1       VARCHAR,
    industry_top2       VARCHAR,
    industry_top3       VARCHAR,
    locode              VARCHAR
);

CREATE TABLE IF NOT EXISTS dim_port (
    portid              VARCHAR PRIMARY KEY,   -- 'port1'..'portNNNN'
    fullname            VARCHAR,
    portname            VARCHAR,
    country             VARCHAR,
    iso3                VARCHAR,
    continent           VARCHAR,
    lat                 DOUBLE,
    lon                 DOUBLE,
    vessel_count_total          BIGINT,
    vessel_count_container      BIGINT,
    vessel_count_dry_bulk       BIGINT,
    vessel_count_general_cargo  BIGINT,
    vessel_count_roro           BIGINT,
    vessel_count_tanker         BIGINT,
    share_country_maritime_import  DOUBLE,
    share_country_maritime_export  DOUBLE,
    industry_top1       VARCHAR,
    industry_top2       VARCHAR,
    industry_top3       VARCHAR,
    locode              VARCHAR
);

-- ---------------------------------------------------------------------------
-- Daily facts. PortWatch publishes daily granularity, refreshed weekly.
-- 'date' arrives as an ISO 'YYYY-MM-DD' string upstream; stored as DATE here.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS fct_chokepoint_daily (
    portid                  VARCHAR,
    date                    DATE,
    portname                VARCHAR,
    n_container             BIGINT,
    n_dry_bulk              BIGINT,
    n_general_cargo         BIGINT,
    n_roro                  BIGINT,
    n_tanker                BIGINT,
    n_cargo                 BIGINT,
    n_total                 BIGINT,
    capacity_container      BIGINT,
    capacity_dry_bulk       BIGINT,
    capacity_general_cargo  BIGINT,
    capacity_roro           BIGINT,
    capacity_tanker         BIGINT,
    capacity_cargo          BIGINT,
    capacity_total          BIGINT,
    PRIMARY KEY (portid, date)
);

CREATE TABLE IF NOT EXISTS fct_port_daily (
    portid                    VARCHAR,
    date                      DATE,
    portname                  VARCHAR,
    portcalls_container       BIGINT,
    portcalls_dry_bulk        BIGINT,
    portcalls_general_cargo   BIGINT,
    portcalls_roro            BIGINT,
    portcalls_tanker          BIGINT,
    portcalls_cargo           BIGINT,
    portcalls_total           BIGINT,
    import_container          BIGINT,
    import_dry_bulk           BIGINT,
    import_general_cargo      BIGINT,
    import_roro               BIGINT,
    import_tanker             BIGINT,
    import_cargo              BIGINT,
    import_total              BIGINT,
    export_container          BIGINT,
    export_dry_bulk           BIGINT,
    export_general_cargo      BIGINT,
    export_roro               BIGINT,
    export_tanker             BIGINT,
    export_cargo              BIGINT,
    export_total              BIGINT,
    PRIMARY KEY (portid, date)
);

-- ---------------------------------------------------------------------------
-- Write-Audit-Publish staging. Fresh PortWatch pulls land HERE first; only a
-- clean data-quality audit (wap.py) promotes them into the fct_* tables above
-- inside a single transaction. Same columns/keys as the prod facts — a staging
-- row is just an un-audited prod row. Kept empty between runs (truncated on the
-- successful swap), so it never serves traffic.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS stg_chokepoint_daily (
    portid                  VARCHAR,
    date                    DATE,
    portname                VARCHAR,
    n_container             BIGINT,
    n_dry_bulk              BIGINT,
    n_general_cargo         BIGINT,
    n_roro                  BIGINT,
    n_tanker                BIGINT,
    n_cargo                 BIGINT,
    n_total                 BIGINT,
    capacity_container      BIGINT,
    capacity_dry_bulk       BIGINT,
    capacity_general_cargo  BIGINT,
    capacity_roro           BIGINT,
    capacity_tanker         BIGINT,
    capacity_cargo          BIGINT,
    capacity_total          BIGINT,
    PRIMARY KEY (portid, date)
);

CREATE TABLE IF NOT EXISTS stg_port_daily (
    portid                    VARCHAR,
    date                      DATE,
    portname                  VARCHAR,
    portcalls_container       BIGINT,
    portcalls_dry_bulk        BIGINT,
    portcalls_general_cargo   BIGINT,
    portcalls_roro            BIGINT,
    portcalls_tanker          BIGINT,
    portcalls_cargo           BIGINT,
    portcalls_total           BIGINT,
    import_container          BIGINT,
    import_dry_bulk           BIGINT,
    import_general_cargo      BIGINT,
    import_roro               BIGINT,
    import_tanker             BIGINT,
    import_cargo              BIGINT,
    import_total              BIGINT,
    export_container          BIGINT,
    export_dry_bulk           BIGINT,
    export_general_cargo      BIGINT,
    export_roro               BIGINT,
    export_tanker             BIGINT,
    export_cargo              BIGINT,
    export_total              BIGINT,
    PRIMARY KEY (portid, date)
);

-- ---------------------------------------------------------------------------
-- Operational metadata (provenance + source health for honest UI tiles).
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS meta_ingest_runs (
    run_id        VARCHAR,
    kind          VARCHAR,        -- 'dims' | 'chokepoint_daily' | 'port_daily' | 'backfill'
    started_at    TIMESTAMP,
    finished_at   TIMESTAMP,
    rows_written  BIGINT,
    status        VARCHAR,        -- 'ok' | 'error'
    detail        VARCHAR
);

CREATE TABLE IF NOT EXISTS meta_source_status (
    source         VARCHAR PRIMARY KEY,   -- e.g. 'portwatch'
    last_success   TIMESTAMP,
    max_data_date  DATE,                  -- the data's own freshness, shown in UI
    status         VARCHAR,               -- 'ok' | 'stale' | 'error'
    note           VARCHAR
);

-- One row per Write-Audit-Publish promotion: the lineage trail. ``lineage_run_id``
-- is deterministic (derived from the staged data's max date + row counts), so the
-- same data re-published yields the same id, and a published map can be traced back
-- to the exact audit that cleared it.
CREATE TABLE IF NOT EXISTS meta_publish_runs (
    lineage_run_id VARCHAR,
    promoted_at    TIMESTAMP,
    verdict        VARCHAR,        -- 'pass' | 'fail'
    checks_run     BIGINT,
    rows_promoted  BIGINT,
    detail         VARCHAR         -- JSON: per-check {name, ok, severity, message}
);
