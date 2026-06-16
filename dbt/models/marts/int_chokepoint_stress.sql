{{ config(materialized='view') }}

-- int_chokepoint_stress — the per-(portid, date) substrate of the Global Ocean
-- Freight Stress Index, for the trailing {{ var('stress_window_days') }}-day window.
-- A faithful SQL re-expression of narrative/stress.py:
--   * "normal" throughput = {{ var('stress_normal_pctile') }}-pctile of the chokepoint's
--     FULL record (quantile_cont = linear interpolation, matching export_timeseries'
--     quantile_cont over all of fct_chokepoint_daily) — anchored long, NOT the trailing
--     window, so a sustained collapse keeps driving the index (H1-C),
--   * economic weight  = a chokepoint's normal vessel-CAPACITY (DWT) share of the total
--     (bigger ships carry more trade) — matches stress.compute's cap_normal weighting,
--   * raw stress       = deviation-from-normal squashed into [0,1], ignored below
--     DEV_FLOOR ({{ var('stress_dev_floor') }}) and saturated at DEV_SATURATE
--     ({{ var('stress_dev_saturate') }}) — stress._stress,
--   * stress           = causal trailing {{ var('stress_smooth_days') }}-day mean of
--     the raw series (no future leakage) — stress._smooth.
-- PortWatch publishes all 28 chokepoints on a dense daily date axis, so the Python
-- forward-fill alignment (timeseries._align) is an identity here and the numbers
-- reconcile to stress.compute(). The downstream index lives in
-- mart_freight_stress_index; this view also exposes per-chokepoint contributors.

with bounds as (
    select max(date) as max_date from {{ ref('stg_chokepoint_daily') }}
),

obs as (
    select
        s.portid,
        c.fullname                          as name,
        c.lat,
        c.lon,
        s.date,
        cast(s.n_total as double)           as value
    from {{ ref('stg_chokepoint_daily') }} s
    join {{ ref('stg_chokepoints') }} c on s.portid = c.portid
    cross join bounds b
    -- window = dates strictly after (max_date - window), matching
    -- export_timeseries' `date > (max(date) - WINDOW_DAYS)`.
    where s.date > b.max_date - {{ var('stress_window_days') }}
),

-- "normal" + capacity basis are anchored to the chokepoint's FULL record (no window),
-- matching export_timeseries' quantile_cont over all of fct_chokepoint_daily (H1-C):
-- anchoring long is what keeps a sustained collapse driving the index.
long_obs as (
    select
        portid,
        cast(n_total as double)        as n_value,
        cast(capacity_total as double) as cap_value
    from {{ ref('stg_chokepoint_daily') }}
),

normals as (
    select
        portid,
        quantile_cont(n_value, {{ var('stress_normal_pctile') }})   as normal,
        quantile_cont(cap_value, {{ var('stress_normal_pctile') }}) as cap_normal
    from long_obs
    group by portid
),

-- economic weight = normal DWT-capacity share (bigger ships carry more trade), NOT
-- vessel-count share — matches stress.compute's cap_normal weighting. A chokepoint
-- with no capacity data falls back to its vessel-count normal, exactly as Python does.
weighted as (
    select
        portid,
        normal,
        coalesce(cap_normal, normal)
            / nullif(sum(coalesce(cap_normal, normal)) over (), 0) as weight
    from normals
),

raw_stress as (
    select
        o.portid,
        o.name,
        o.lat,
        o.lon,
        o.date,
        o.value,
        w.normal,
        w.weight,
        case
            when w.normal <= 0 then 0.0
            when abs(o.value - w.normal) / w.normal <= {{ var('stress_dev_floor') }} then 0.0
            else least(
                1.0,
                (abs(o.value - w.normal) / w.normal - {{ var('stress_dev_floor') }})
                    / ({{ var('stress_dev_saturate') }} - {{ var('stress_dev_floor') }})
            )
        end as stress_raw
    from obs o
    join weighted w on o.portid = w.portid
)

select
    portid,
    name,
    lat,
    lon,
    date,
    value,
    normal,
    weight,
    stress_raw,
    avg(stress_raw) over (
        partition by portid order by date
        rows between {{ var('stress_smooth_days') - 1 }} preceding and current row
    ) as stress
from raw_stress
