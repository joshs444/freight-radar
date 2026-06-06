-- mart_freight_stress_index — the Global Ocean Freight Stress Index (0-100), one
-- row per day across the trailing window. Faithful re-expression of
-- narrative/stress.py compute(): the daily index BLENDS economic-weighted breadth
-- (how broadly the system is stressed) and worst-chokepoint depth (how bad the
-- single worst artery is):
--     breadth(t) = Σ_i weight_i · stress_i(t)
--     depth(t)   = max_i stress_i(t)
--     index(t)   = 100 · (BREADTH_W · breadth + DEPTH_W · depth)
-- The label thresholds (calm/elevated/high/severe) and the disrupted-at cutoff
-- mirror stress._label / DISRUPTED_AT. The label is derived from the *rounded*
-- index, exactly as stress.compute does (`_label(history[-1])`).

with per_day as (
    select
        date,
        sum(weight * stress)                                                as breadth,
        max(stress)                                                         as depth,
        count(*)                                                            as n_chokepoints,
        sum(case when stress >= {{ var('stress_disrupted_at') }} then 1 else 0 end) as n_disrupted
    from {{ ref('int_chokepoint_stress') }}
    group by date
),

scored as (
    select
        date,
        -- round_even = banker's rounding, matching Python's round() in stress.compute().
        round_even(100 * breadth, 1)                                        as breadth,
        round_even(100 * depth, 1)                                          as depth,
        round_even(100 * ({{ var('stress_breadth_w') }} * breadth
                        + {{ var('stress_depth_w') }} * depth), 1)          as index_value,
        n_chokepoints,
        n_disrupted
    from per_day
)

select
    date,
    index_value,
    breadth,
    depth,
    case
        when index_value >= 55 then 'severe'
        when index_value >= 35 then 'high'
        when index_value >= 15 then 'elevated'
        else 'calm'
    end                                                                     as label,
    n_chokepoints,
    n_disrupted
from scored
order by date
