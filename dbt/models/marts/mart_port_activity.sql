-- mart_port_activity — the per-port latest-activity snapshot the globe reads:
-- each geometry-carrying port's most recent daily port-call count + cargo mix +
-- IMF national-dependence shares. A faithful re-expression of
-- export_snapshot._ports (one row per port that carries lat/lon):
--   * recent = each port's latest day (arg_max at its own max date),
--   * only ports with geometry (has_geometry) — the same lat/lon-not-null filter,
--   * vessels / portcalls default to 0 when absent, shares round to 1 dp when present
--     (NULL otherwise), exactly as the Python None-guards do.

with recent as (
    select
        portid,
        max(date)                                   as latest_date,
        arg_max(portcalls_total, date)              as portcalls,
        arg_max(portcalls_container, date)          as portcalls_container,
        arg_max(portcalls_tanker, date)             as portcalls_tanker,
        arg_max(portcalls_dry_bulk, date)           as portcalls_dry_bulk,
        arg_max(portcalls_general_cargo, date)      as portcalls_general_cargo,
        arg_max(portcalls_roro, date)               as portcalls_roro
    from {{ ref('stg_port_daily') }}
    group by portid
)

select
    d.portid,
    d.portname                                       as name,
    d.country,
    d.lat,
    d.lon,
    r.latest_date                                    as as_of,
    coalesce(d.vessel_count_total, 0)                as vessels,
    coalesce(r.portcalls, 0)                         as portcalls,
    r.portcalls_container,
    r.portcalls_tanker,
    r.portcalls_dry_bulk,
    r.portcalls_general_cargo,
    r.portcalls_roro,
    -- National-dependence shares (0-100%) are passthrough IMF dim attributes, not
    -- computed pipeline outputs — export_snapshot._ports rounds them to 1 dp only for
    -- JSON compactness. The mart carries FULL PRECISION (display rounding is a serving
    -- concern), so these reconcile exactly to the source dim.
    d.share_country_maritime_import                  as share_import,
    d.share_country_maritime_export                  as share_export
from {{ ref('stg_ports') }} d
join recent r on d.portid = r.portid
where d.has_geometry
