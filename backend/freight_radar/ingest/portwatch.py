"""Load the daily fact layers (chokepoints + ports) into DuckDB.

The upstream totals are named ``capacity`` / ``portcalls`` / ``import`` / ``export``
— all DuckDB reserved words — so we rename them to ``*_total`` on the way in.
``date`` arrives as an ISO 'YYYY-MM-DD' string and is cast to DATE by the insert.
"""

from __future__ import annotations

from datetime import date

import pandas as pd

from ..arcgis import ArcGISClient
from ..config import SERVICES
from ..storage.db import upsert_df

# upstream attr name -> our column name (order defines the frame's column order)
_CHOKE_MAP = {
    "portid": "portid",
    "date": "date",
    "portname": "portname",
    "n_container": "n_container",
    "n_dry_bulk": "n_dry_bulk",
    "n_general_cargo": "n_general_cargo",
    "n_roro": "n_roro",
    "n_tanker": "n_tanker",
    "n_cargo": "n_cargo",
    "n_total": "n_total",
    "capacity_container": "capacity_container",
    "capacity_dry_bulk": "capacity_dry_bulk",
    "capacity_general_cargo": "capacity_general_cargo",
    "capacity_roro": "capacity_roro",
    "capacity_tanker": "capacity_tanker",
    "capacity_cargo": "capacity_cargo",
    "capacity": "capacity_total",
}

_PORT_MAP = {
    "portid": "portid",
    "date": "date",
    "portname": "portname",
    "portcalls_container": "portcalls_container",
    "portcalls_dry_bulk": "portcalls_dry_bulk",
    "portcalls_general_cargo": "portcalls_general_cargo",
    "portcalls_roro": "portcalls_roro",
    "portcalls_tanker": "portcalls_tanker",
    "portcalls_cargo": "portcalls_cargo",
    "portcalls": "portcalls_total",
    "import_container": "import_container",
    "import_dry_bulk": "import_dry_bulk",
    "import_general_cargo": "import_general_cargo",
    "import_roro": "import_roro",
    "import_tanker": "import_tanker",
    "import_cargo": "import_cargo",
    "import": "import_total",
    "export_container": "export_container",
    "export_dry_bulk": "export_dry_bulk",
    "export_general_cargo": "export_general_cargo",
    "export_roro": "export_roro",
    "export_tanker": "export_tanker",
    "export_cargo": "export_cargo",
    "export": "export_total",
}


def _to_frame(rows: list[dict], colmap: dict[str, str], *, label: str) -> pd.DataFrame:
    df = pd.DataFrame(rows)
    # Guard against silent schema drift: a renamed/dropped upstream column would
    # otherwise be quietly skipped by ``keep`` and land all-NULL on insert. Fail
    # loudly instead (only when rows exist — an empty window is a fetch concern,
    # caught by the coverage + completeness gates, not a column-drop).
    if not df.empty:
        missing = [c for c in colmap if c not in df.columns]
        if missing:
            raise ValueError(
                f"{label}: PortWatch payload missing mapped columns {missing} "
                f"— upstream schema drift; refusing to insert all-NULL"
            )
    keep = [c for c in colmap if c in df.columns]
    df = df[keep].rename(columns={k: colmap[k] for k in keep})
    # date stays a string here; DuckDB casts 'YYYY-MM-DD' -> DATE on insert.
    return df.convert_dtypes()


async def load_chokepoint_daily(
    con, client: ArcGISClient, start: date, end: date
) -> int:
    rows = await client.query_date_window(
        SERVICES["daily_chokepoints"], start, end, chunk_days=45, verify_count=True
    )
    return upsert_df(con, "fct_chokepoint_daily", _to_frame(rows, _CHOKE_MAP, label="fct_chokepoint_daily"))


async def load_port_daily(con, client: ArcGISClient, start: date, end: date) -> int:
    rows = await client.query_date_window(
        SERVICES["daily_ports"], start, end, chunk_days=20, verify_count=True
    )
    return upsert_df(con, "fct_port_daily", _to_frame(rows, _PORT_MAP, label="fct_port_daily"))
