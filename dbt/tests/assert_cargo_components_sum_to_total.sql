-- Cargo-mix reconciliation invariant (the warehouse-side analogue of the D2
-- silent-column-drop guard, test_etl_guards.test_*_frame_raises_on_missing_*).
-- PortWatch breaks every count into 5 leaf vessel types that must reconcile to the
-- headline totals; if an upstream rename/drop silently zeroed or shifted a leaf, the
-- sums stop matching. We assert the same identity export_snapshot relies on when it
-- builds a cargo mix:
--     container + dry_bulk + general_cargo + roro = *_cargo
--     *_cargo + tanker                            = *_total
-- for both the chokepoint (n_*) and port (portcalls_*) grain. Import/export
-- breakdowns are NOT guaranteed to sum upstream, so they are intentionally not
-- asserted (see stg_port_daily). A breach returns a row and fails `dbt build`.

select 'chokepoint' as grain, portid, cast(date as varchar) as date
from {{ ref('stg_chokepoint_daily') }}
where n_container + n_dry_bulk + n_general_cargo + n_roro <> n_cargo
   or n_cargo + n_tanker <> n_total

union all

select 'port' as grain, portid, cast(date as varchar) as date
from {{ ref('stg_port_daily') }}
where portcalls_container + portcalls_dry_bulk + portcalls_general_cargo + portcalls_roro <> portcalls_cargo
   or portcalls_cargo + portcalls_tanker <> portcalls_total
