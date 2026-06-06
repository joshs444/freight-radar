-- Port reference dim, standardized. The marts and the join-coverage guard only
-- consider ports that carry geometry (lat/lon not null), matching the Python
-- export_snapshot._ports filter; a `has_geometry` flag makes that explicit while
-- keeping every port row available for coverage accounting.

with source as (
    select * from {{ source('freight_radar', 'dim_port') }}
)

select
    portid,
    fullname,
    portname,
    country,
    iso3,
    continent,
    cast(lat as double)                              as lat,
    cast(lon as double)                              as lon,
    cast(vessel_count_total as bigint)               as vessel_count_total,
    cast(share_country_maritime_import as double)    as share_country_maritime_import,
    cast(share_country_maritime_export as double)    as share_country_maritime_export,
    industry_top1,
    industry_top2,
    industry_top3,
    locode,
    (lat is not null and lon is not null)            as has_geometry
from source
