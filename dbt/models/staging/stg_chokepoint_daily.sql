-- Standardized daily chokepoint transits: one row per (portid, date). Cleans the
-- raw fact (explicit casts, a surrogate key for the PK test) and exposes exactly
-- the columns the marts re-express. The cargo leaf counts sum to n_cargo, and
-- n_cargo + n_tanker = n_total — invariants enforced in
-- tests/assert_cargo_components_sum_to_total.sql.

with source as (
    select * from {{ source('freight_radar', 'fct_chokepoint_daily') }}
)

select
    -- (portid, date) is the warehouse PK; a surrogate key lets the built-in
    -- `unique` test stand in for the WAP no_duplicate_keys check.
    portid || '|' || cast(date as varchar)   as entity_day_key,
    portid,
    cast(date as date)                        as date,
    portname,
    cast(n_container        as bigint)        as n_container,
    cast(n_dry_bulk         as bigint)        as n_dry_bulk,
    cast(n_general_cargo    as bigint)        as n_general_cargo,
    cast(n_roro             as bigint)        as n_roro,
    cast(n_tanker           as bigint)        as n_tanker,
    cast(n_cargo            as bigint)        as n_cargo,
    cast(n_total            as bigint)        as n_total,
    cast(capacity_total     as bigint)        as capacity_total
from source
