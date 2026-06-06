-- D1 ETL guard — portid -> geometry join coverage gate.
-- Re-expresses storage.db.join_coverage() + temporal.activities._assert_join_coverage
-- (test_etl_guards.test_join_coverage_gate_*): coverage = the fraction of DISTINCT fact
-- portids that resolve to a reference dim row, asserted >= MIN_JOIN_COVERAGE
-- ({{ var('min_join_coverage') }}) for BOTH the chokepoint and the port grain. This
-- mirrors the Python exactly — `WITH f AS (SELECT DISTINCT portid ...) COUNT(d.portid) /
-- COUNT(*)` — i.e. "what fraction of unique entities in the data carry geometry", NOT a
-- row-weighted average. In Python a breach raises *non-retryably* (a data-quality fact,
-- not a transient error); here it returns a row and fails `dbt build`. The boundary
-- (coverage == threshold) passes, matching test_join_coverage_gate_passes_at_or_above_threshold.

with coverage as (
    select
        'chokepoint' as grain,
        cast(count(d.portid) as double) / nullif(count(*), 0) as cov
    from (select distinct portid from {{ ref('stg_chokepoint_daily') }}) f
    left join {{ ref('stg_chokepoints') }} d on f.portid = d.portid

    union all

    select
        'port' as grain,
        cast(count(p.portid) as double) / nullif(count(*), 0) as cov
    from (select distinct portid from {{ ref('stg_port_daily') }}) f
    left join {{ ref('stg_ports') }} p on f.portid = p.portid
)

select grain, cov
from coverage
where cov < {{ var('min_join_coverage') }}
