"""Central config for Freight Radar ingest.

Everything the app reads is derived from the four PortWatch ArcGIS layers below.
These endpoints were verified live during design (see PLAN.md). The org id is
``weJ1QsnbMYJlCHdG`` — the older ``weJ1QsnbMRgolu6q`` 400s, do not use it.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- paths -----------------------------------------------------------------
PACKAGE_DIR = Path(__file__).resolve().parent          # backend/freight_radar
BACKEND_DIR = PACKAGE_DIR.parent                       # backend
REPO_ROOT = BACKEND_DIR.parent                         # freight-radar
DATA_DIR = REPO_ROOT / "data"
DEFAULT_DB_PATH = DATA_DIR / "freight_radar.duckdb"

# Where the workflow publishes the static JSON the frontend reads.
PUBLISH_DIR = REPO_ROOT / "frontend" / "public" / "data"


def db_path() -> Path:
    """DuckDB path, overridable via env (docker volume / tests)."""
    return Path(os.environ.get("FREIGHT_RADAR_DB", str(DEFAULT_DB_PATH)))


def publish_dir() -> Path:
    """Publish dir, overridable via env (docker volume / tests)."""
    return Path(os.environ.get("FREIGHT_RADAR_PUBLISH_DIR", str(PUBLISH_DIR)))

# --- ArcGIS backbone -------------------------------------------------------
ARCGIS_HOST = "https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services"

SERVICES = {
    "daily_chokepoints": "Daily_Chokepoints_Data",      # time series, NO geometry
    "daily_ports": "Daily_Ports_Data",                  # time series, NO geometry
    "chokepoints_db": "PortWatch_chokepoints_database",  # 28 rows, lat/lon in attrs
    "ports_db": "PortWatch_ports_database",              # ~2065 rows, lat/lon in attrs
    "disruptions_db": "portwatch_disruptions_database",  # curated events (used in Wave 5)
}

PAGE_SIZE = 1000          # ArcGIS hard cap per request
DEFAULT_CONCURRENCY = 6   # bounded — do not hammer the public service
BACKFILL_DAYS = 180       # enough history for STL(period=7) + 28d rolling baselines
INCREMENTAL_REPULL_DAYS = 14  # PortWatch values are revisable estimates

# Minimum portid->geometry join coverage we assert the data still honors.
MIN_JOIN_COVERAGE = 0.95

# Reference-layer fields we keep (lat/lon are WGS84 decimal degrees in attrs).
DIM_OUT_FIELDS = (
    "portid,fullname,portname,country,ISO3,continent,lat,lon,"
    "vessel_count_total,industry_top1,industry_top2,industry_top3,LOCODE"
)
