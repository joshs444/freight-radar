-- Freight Radar — detection output table (Wave 2).
-- Created lazily by the detector (CREATE TABLE IF NOT EXISTS); NOT part of the
-- Wave-0 storage/schema.sql so the ingest backbone stays untouched.
--
-- flag_id is dedup-stable per (kind, portid, ISO-week): a given anomaly keeps the
-- same id across reruns within its week, so Wave 3's attribution ledger and the
-- INSERT OR REPLACE upsert below both no-op on an identical rerun.

CREATE TABLE IF NOT EXISTS fct_flags (
    flag_id        VARCHAR PRIMARY KEY,   -- sha1(kind|portid|isoYear-Wweek)[:16]
    kind           VARCHAR,               -- chokepoint_transit_collapse | _spike | port_activity_drop | port_congestion_spike
    entity         VARCHAR,               -- human name (e.g. 'Suez Canal')
    portid         VARCHAR,
    lat            DOUBLE,
    lon            DOUBLE,
    severity       INTEGER,               -- 0..100, see SEVERITY docstring in detectors.py
    headline       VARCHAR,
    brief_md       VARCHAR,               -- markdown brief; numbers are Python-computed
    metric         VARCHAR,               -- 'n_total' | 'portcalls_total'
    value          DOUBLE,                -- latest raw value on as_of
    baseline       DOUBLE,                -- trailing-28d mean of the raw value
    pct_change     DOUBLE,                -- (value - baseline) / baseline * 100
    zscore         DOUBLE,                -- rolling z of the STL residual
    as_of          DATE,                  -- the data date the anomaly was measured on
    detected_date  DATE,                  -- the date detection ran (today)
    source         VARCHAR,
    method         VARCHAR,
    lifecycle      VARCHAR,               -- 'new' for Wave 2 (lifecycle lands in Wave 5)
    computed_at    TIMESTAMP
);
