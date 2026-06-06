-- Chokepoint reference dim, standardized. lat/lon are WGS84 decimal degrees.
-- vessel_count_total is the all-time fleet base used as the detector's economic
-- weight; share_country_maritime_* are 0-100% IMF national-dependence scores.

with source as (
    select * from {{ source('freight_radar', 'dim_chokepoint') }}
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
    locode
from source
