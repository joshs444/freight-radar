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
    vessel_count_total  BIGINT,
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
    vessel_count_total  BIGINT,
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
