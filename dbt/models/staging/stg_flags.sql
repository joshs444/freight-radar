-- Detected anomalies, standardized. Every numeric field (value, baseline,
-- pct_change, zscore, severity) is Python-computed by the detection brain
-- (detect/detectors.py) — dbt only cleans + serves them; no model is in the
-- number path. One row per (kind, portid, ISO-week): flag_id is the stable PK.

with source as (
    select * from {{ source('freight_radar', 'fct_flags') }}
)

select
    flag_id,
    kind,
    entity,
    portid,
    cast(lat as double)         as lat,
    cast(lon as double)         as lon,
    cast(severity as integer)   as severity,
    headline,
    metric,
    cast(value as double)       as value,
    cast(baseline as double)    as baseline,
    cast(pct_change as double)  as pct_change,
    cast(zscore as double)      as zscore,
    cast(as_of as date)         as as_of,
    cast(detected_date as date) as detected_date,
    lifecycle,
    source                      as data_source,
    method
from source
