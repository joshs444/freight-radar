"""Tests for the natural-hazard / official-event layer (matching + corroboration).

No network: we feed synthetic GDACS-shaped raw events through the same build +
corroborate functions the live fetch uses.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from freight_radar import hazards as H


def _ms(y, m, d) -> int:
    return int(datetime(y, m, d, tzinfo=timezone.utc).timestamp() * 1000)


PORTS = {"port10": "Manila", "port11": "Subic Bay", "port99": "Rotterdam"}
CHOKES = [
    {"portid": "cp_luzon", "name": "Luzon Strait", "lat": 20.5, "lon": 121.0},
    {"portid": "cp_suez", "name": "Suez Canal", "lat": 30.6, "lon": 32.3},
]


def _raw(eventtype, alert, name, frm, to, lat, lon, affected):
    return {"eventid": hash(name) & 0xffff, "eventtype": eventtype, "alertlevel": alert,
            "eventname": name, "htmlname": name, "country": "X",
            "fromdate": _ms(*frm), "todate": _ms(*to), "lat": lat, "long": lon,
            "n_affectedports": len(affected.split(";")) if affected else 0,
            "affectedports": affected, "affectedpopulation": 1000}


def test_parse_affected_handles_separators():
    assert H._parse_affected("port10; port11, port99") == ["port10", "port11", "port99"]
    assert H._parse_affected("") == []
    assert H._parse_affected("notaport; port5") == ["port5"]


def test_build_matches_ports_and_chokepoint_proximity():
    as_of = date(2026, 1, 15)
    raw = [_raw("TC", "RED", "Cyclone A", (2026, 1, 1), (2026, 1, 5), 20.4, 121.2, "port10; port11")]
    evs = H.build_events(raw, PORTS, CHOKES, as_of)
    assert len(evs) == 1
    e = evs[0]
    assert {p["portid"] for p in e["affected_ports"]} == {"port10", "port11"}
    assert any(c["portid"] == "cp_luzon" for c in e["near_chokepoints"])  # within 350km
    assert all(c["portid"] != "cp_suez" for c in e["near_chokepoints"])   # far away


def test_old_events_dropped_and_non_infra_dropped():
    as_of = date(2026, 6, 1)
    raw = [
        _raw("TC", "RED", "Ancient", (2024, 1, 1), (2024, 1, 5), 20.4, 121.2, "port10"),   # too old
        _raw("FL", "ORANGE", "Nowhere", (2026, 5, 20), (2026, 5, 22), -40.0, 0.0, ""),     # no infra
    ]
    assert H.build_events(raw, PORTS, CHOKES, as_of) == []


def test_corroborate_only_when_contemporaneous():
    as_of = date(2026, 1, 15)
    raw = [_raw("TC", "RED", "Cyclone A", (2026, 1, 1), (2026, 1, 5), 20.4, 121.2, "port10")]
    evs = H.build_events(raw, PORTS, CHOKES, as_of)

    # a Manila flag dated within the event window → corroborated
    near = [{"portid": "port10", "entity": "Manila", "as_of": "2026-01-04", "lifecycle": "ongoing"}]
    assert H.corroborate(near, evs) == 1
    assert near[0]["official_event"]["name"] == "Cyclone A"
    assert near[0]["official_event"]["alertlevel"] == "RED"

    # same port but a flag dated 4 months later → NOT corroborated (no false causation)
    far = [{"portid": "port10", "entity": "Manila", "as_of": "2026-05-20", "lifecycle": "ongoing"}]
    assert H.corroborate(far, evs) == 0
    assert "official_event" not in far[0]

    # an unrelated port → never corroborated
    other = [{"portid": "port99", "entity": "Rotterdam", "as_of": "2026-01-04", "lifecycle": "ongoing"}]
    assert H.corroborate(other, evs) == 0
