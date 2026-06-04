"""Phase D — ETL hardening guards. Each turns a silent failure into a loud one;
these tests pin the guard logic deterministically (no network, no DuckDB).

  D1  join-coverage gate in the durable Temporal path (was log-only)
  D2  silent-column-drop assertion in both ingest frames
  D3  fetch-completeness check (a dropped page is now a hard, retryable failure)
"""

from __future__ import annotations

import pytest
from temporalio.exceptions import ApplicationError

from freight_radar.arcgis import ArcGISError, _assert_fetch_complete
from freight_radar.config import MIN_JOIN_COVERAGE
from freight_radar.ingest import dims as DIMS
from freight_radar.ingest import portwatch as PW
from freight_radar.temporal.activities import _assert_join_coverage


# --- D1: join-coverage gate --------------------------------------------------


def test_join_coverage_gate_raises_non_retryably_below_threshold():
    low = MIN_JOIN_COVERAGE - 0.10
    with pytest.raises(ApplicationError) as ei:
        _assert_join_coverage(choke_cov=0.99, port_cov=low)
    assert ei.value.non_retryable is True  # a data-quality fact, not a transient error
    assert "port join coverage" in str(ei.value)


def test_join_coverage_gate_passes_at_or_above_threshold():
    assert _assert_join_coverage(0.99, MIN_JOIN_COVERAGE) is None  # boundary is OK


# --- D2: silent-column-drop assertion ---------------------------------------


def test_fact_frame_raises_on_missing_mapped_column():
    colmap = {"portid": "portid", "date": "date", "n_total": "n_total"}
    rows = [{"portid": "c1", "date": "2026-05-31"}]  # n_total renamed/dropped upstream
    with pytest.raises(ValueError) as ei:
        PW._to_frame(rows, colmap, label="fct_chokepoint_daily")
    assert "n_total" in str(ei.value)


def test_fact_frame_passes_when_all_present_and_tolerates_empty():
    colmap = {"portid": "portid", "n_total": "n_total"}
    df = PW._to_frame([{"portid": "c1", "n_total": 5}], colmap, label="x")
    assert list(df.columns) == ["portid", "n_total"] and int(df["n_total"].iloc[0]) == 5
    # an empty window must NOT trip the column guard (it's a fetch concern, not drift)
    assert PW._to_frame([], colmap, label="x").empty


def test_dim_frame_raises_on_missing_non_geometry_column():
    full = {src: f"v_{src}" for src in DIMS._DIM_MAP}
    full["lat"], full["lon"] = "1.0", "2.0"
    ok = DIMS._to_frame([full])
    assert "vessel_count_total" in ok.columns and float(ok["lat"].iloc[0]) == 1.0
    broken = dict(full)
    broken.pop("vessel_count_total")  # a non-geometry field silently renamed
    with pytest.raises(ValueError) as ei:
        DIMS._to_frame([broken])
    assert "vessel_count_total" in str(ei.value)


# --- D3: fetch-completeness check -------------------------------------------


def test_fetch_complete_raises_when_a_page_was_dropped():
    with pytest.raises(ArcGISError) as ei:
        _assert_fetch_complete(n_rows=900, server_count=1000, service="daily_ports", where="w")
    assert "dropped" in str(ei.value)


def test_fetch_complete_passes_on_exact_or_extra_rows():
    # exact match, and a couple extra (concurrent upstream insert) — both fine
    assert _assert_fetch_complete(1000, 1000, "s", "w") is None
    assert _assert_fetch_complete(1002, 1000, "s", "w") is None
