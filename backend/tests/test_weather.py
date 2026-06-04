"""Phase C1 — live tropical-cyclone layer. Deterministic (fixtures, no network):
NHC/GDACS normalization, the NHC-duplicate dedup, and proximity matching to flags.
"""

from __future__ import annotations

from freight_radar import weather as W

NHC = {"activeStorms": [{
    "id": "ep012026", "name": "Amanda", "classification": "TS", "intensity": "35",
    "latitudeNumeric": 12.5, "longitudeNumeric": -130.5,
    "lastUpdate": "2026-06-04T15:00:00.000Z",
    "trackCone": {"issuance": "2026-06-04T15:00:00.000Z",
                  "kmzFile": "https://www.nhc.noaa.gov/storm_graphics/api/EP012026_008adv_CONE.kmz"},
}]}

GDACS = {"features": [
    {"geometry": {"coordinates": [121.0, 23.5]},  # JTWC W-Pacific, active -> KEPT
     "properties": {"eventtype": "TC", "iscurrent": "true", "source": "JTWC",
                    "eventid": 1, "eventname": "SINLAKU-26", "alertlevel": "Red",
                    "severitydata": {"severity": 150.0},
                    "url": {"geometry": "geo", "report": "rep"}}},
    {"geometry": {"coordinates": [-60.5, 20.0]},  # NOAA-sourced -> DROPPED (NHC dup)
     "properties": {"eventtype": "TC", "iscurrent": "true", "source": "NOAA",
                    "eventid": 2, "eventname": "MELISSA-25", "alertlevel": "Orange"}},
    {"geometry": {"coordinates": [100.0, 5.0]},   # not current -> DROPPED
     "properties": {"eventtype": "TC", "iscurrent": "false", "source": "JTWC",
                    "eventid": 3, "eventname": "OLD-25"}},
]}


def test_normalize_nhc_uses_signed_coords_and_converts_knots():
    [s] = W.normalize_nhc(NHC)
    assert s["lat"] == 12.5 and s["lon"] == -130.5  # signed, not the 'N'/'W' strings
    assert s["category"] == "Tropical Storm" and s["basin"] == "E Pacific"
    assert s["max_wind_kmh"] == round(35 * W.KT_TO_KMH) == 65
    assert s["source"] == "NHC" and s["cone_url"].endswith("CONE.kmz")


def test_normalize_gdacs_drops_noaa_dupes_and_inactive():
    storms = W.normalize_gdacs(GDACS)
    assert len(storms) == 1, "only the active JTWC storm survives"
    s = storms[0]
    assert s["name"] == "SINLAKU"          # '-26' year suffix stripped
    assert s["agency"] == "JTWC" and s["source"] == "GDACS"
    assert s["max_wind_kmh"] == 150 and s["basin"].startswith("W Pacific")


def test_attach_storms_matches_only_within_radius_and_skips_resolved():
    storms = W.normalize_gdacs(GDACS)  # one storm near Taiwan (23.5N, 121.0E)
    near = {"flag_id": "a", "entity": "Kaohsiung", "lat": 22.6, "lon": 120.3, "lifecycle": "new"}
    far = {"flag_id": "b", "entity": "Gibraltar", "lat": 36.0, "lon": -5.3, "lifecycle": "new"}
    resolved = {"flag_id": "c", "entity": "Keelung", "lat": 25.1, "lon": 121.7, "lifecycle": "resolved"}
    flags = [near, far, resolved]
    matched = W.attach_storms(flags, storms)
    assert matched == 1
    assert near["live_storm"]["name"] == "SINLAKU" and near["live_storm"]["km"] < 500
    assert "live_storm" not in far
    assert "live_storm" not in resolved  # resolved flags never carry a live storm
