-- mart_chokepoint_pressure — the per-chokepoint "pressure" snapshot the globe and
-- the feed read: each chokepoint's latest transit count vs its own
-- {{ var('baseline_days') }}-day rolling baseline, with the same pct_change /
-- z-score / average-vessel-size figures the app shows. A faithful re-expression of
-- export_snapshot._chokepoints (one row per chokepoint):
--   * recent   = each chokepoint's latest day (arg_max at its own max date),
--   * baseline = mean & sample-stddev of n_total over [max_date - {{ var('baseline_days') }}, max_date),
--   * pct_change / zscore / avg_vessel_size_dwt computed exactly as the Python does
--     (None-guards preserved: a chokepoint with no baseline carries NULLs, not zeros).
-- avg_vessel_size_dwt = capacity_total / n_total — a fleet-mix figure (bigger/smaller
-- transiting ships), NOT utilisation; capacity is a flow, not a ceiling.

with bounds as (
    select max(date) as max_date from {{ ref('stg_chokepoint_daily') }}
),

recent as (
    select
        portid,
        max(date)                            as latest_date,
        arg_max(n_total, date)               as n_total,
        arg_max(n_container, date)           as n_container,
        arg_max(n_tanker, date)              as n_tanker,
        arg_max(n_dry_bulk, date)            as n_dry_bulk,
        arg_max(n_general_cargo, date)       as n_general_cargo,
        arg_max(n_roro, date)                as n_roro,
        arg_max(capacity_total, date)        as capacity_total
    from {{ ref('stg_chokepoint_daily') }}
    group by portid
),

baseline as (
    select
        f.portid,
        avg(f.n_total)            as base_mean,
        stddev_samp(f.n_total)    as base_std
    from {{ ref('stg_chokepoint_daily') }} f
    cross join bounds b
    where f.date >= b.max_date - {{ var('baseline_days') }}
      and f.date <  b.max_date
    group by f.portid
)

select
    d.portid,
    d.fullname                               as name,
    d.country,
    d.lat,
    d.lon,
    d.industry_top1                          as industry,
    d.vessel_count_total,
    r.latest_date                            as as_of,
    r.n_total,
    r.n_container,
    r.n_tanker,
    r.n_dry_bulk,
    r.n_general_cargo,
    r.n_roro,
    r.capacity_total,
    -- None-guards: baseline is NULL (not 0) when no usable history exists, matching
    -- `round(base, 1) if base else None` etc. in export_snapshot._chokepoints.
    -- round_even = banker's rounding (round-half-to-even), matching Python's round()
    -- so the dbt figures reconcile to the published numbers to the last decimal.
    case when b.base_mean is not null and b.base_mean <> 0
         then round_even(b.base_mean, 1) end      as baseline,
    b.base_std,
    case when b.base_mean is not null and b.base_mean <> 0
         then round_even((r.n_total - b.base_mean) / b.base_mean * 100, 1) end as pct_change,
    case when b.base_mean is not null and b.base_std is not null and b.base_std <> 0
         then round_even((r.n_total - b.base_mean) / b.base_std, 2) end        as zscore,
    case when r.capacity_total is not null and r.n_total > 0
         then cast(round_even(cast(r.capacity_total as double) / r.n_total, 0) as bigint) end as avg_vessel_size_dwt
from {{ ref('stg_chokepoints') }} d
join recent r on d.portid = r.portid
left join baseline b on d.portid = b.portid
order by r.n_total desc
