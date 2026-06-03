"""Load the reference dimensions: 28 chokepoints + ~2065 ports, with lat/lon.

These are the ONLY source of geometry — the daily fact layers carry none, so the
``portid`` join to these tables is mandatory (PLAN.md asserts >95% coverage).
"""

from __future__ import annotations

import pandas as pd

from ..arcgis import ArcGISClient
from ..config import DIM_OUT_FIELDS, SERVICES
from ..storage.db import upsert_df

# upstream attr name -> our column name
_DIM_MAP = {
    "portid": "portid",
    "fullname": "fullname",
    "portname": "portname",
    "country": "country",
    "ISO3": "iso3",
    "continent": "continent",
    "lat": "lat",
    "lon": "lon",
    "vessel_count_total": "vessel_count_total",
    "industry_top1": "industry_top1",
    "industry_top2": "industry_top2",
    "industry_top3": "industry_top3",
    "LOCODE": "locode",
}


def _to_frame(rows: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    df = df[[c for c in _DIM_MAP if c in df.columns]].rename(columns=_DIM_MAP)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    return df.convert_dtypes()


async def fetch_dim(client: ArcGISClient, service_key: str) -> pd.DataFrame:
    rows = await client.query_all(SERVICES[service_key], out_fields=DIM_OUT_FIELDS)
    return _to_frame(rows)


async def load_dims(con, client: ArcGISClient) -> dict[str, int]:
    """Fetch + upsert both dimension tables. Returns rows written per table."""
    choke = await fetch_dim(client, "chokepoints_db")
    ports = await fetch_dim(client, "ports_db")

    # Geometry must be present — it is the whole point of these tables.
    for name, df in (("dim_chokepoint", choke), ("dim_port", ports)):
        missing = int(df["lat"].isna().sum() + df["lon"].isna().sum())
        if missing:
            raise ValueError(f"{name}: {missing} null lat/lon values in reference layer")

    return {
        "dim_chokepoint": upsert_df(con, "dim_chokepoint", choke),
        "dim_port": upsert_df(con, "dim_port", ports),
    }
