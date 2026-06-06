-- mart_active_flags — the "current issues" feed: detected anomalies that are still
-- live (lifecycle hysteresis, Wave 5), ranked by severity. This is a SERVING
-- re-expression, not a re-computation: every numeric field (severity, value,
-- baseline, pct_change, zscore) is produced by the Python detection brain
-- (detect/detectors.py) and only cleaned + ordered here — no dbt model sits in the
-- number path for detection. The severity-desc ranking mirrors how the app and
-- export_snapshot._preview_flags surface the top current issues.

with flags as (
    select * from {{ ref('stg_flags') }}
)

select
    flag_id,
    kind,
    entity,
    portid,
    lat,
    lon,
    severity,
    headline,
    metric,
    value,
    baseline,
    pct_change,
    zscore,
    as_of,
    detected_date,
    lifecycle,
    data_source,
    method,
    row_number() over (
        order by severity desc, abs(coalesce(zscore, 0)) desc, flag_id
    ) as severity_rank
from flags
where lifecycle <> 'resolved'
order by severity_rank
