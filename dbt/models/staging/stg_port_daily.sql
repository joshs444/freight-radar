-- Standardized daily port activity: one row per (portid, date). The portcalls leaf
-- counts sum to portcalls_cargo, and portcalls_cargo + portcalls_tanker =
-- portcalls_total (enforced in tests/assert_cargo_components_sum_to_total.sql).
-- (import_*/export_* breakdowns are NOT guaranteed to sum upstream, so they are
-- carried as-is and not asserted.)

with source as (
    select * from {{ source('freight_radar', 'fct_port_daily') }}
)

select
    portid || '|' || cast(date as varchar)        as entity_day_key,
    portid,
    cast(date as date)                            as date,
    portname,
    cast(portcalls_container     as bigint)       as portcalls_container,
    cast(portcalls_dry_bulk      as bigint)       as portcalls_dry_bulk,
    cast(portcalls_general_cargo as bigint)       as portcalls_general_cargo,
    cast(portcalls_roro          as bigint)       as portcalls_roro,
    cast(portcalls_tanker        as bigint)       as portcalls_tanker,
    cast(portcalls_cargo         as bigint)       as portcalls_cargo,
    cast(portcalls_total         as bigint)       as portcalls_total
from source
