"""Resolve user-supplied port tokens to canonical PortWatch ports.

The v1 exposure model matched ports by exact region/name STRING, so any real-world
CSV (LOCODEs, alternate spellings, no region column) silently resolved to zero
exposure — a credibility trap. This resolver accepts whatever a user actually has —
a UN/LOCODE ("NLRTM" or "NL RTM"), a portid, or a port name — and maps it to the
canonical dim_port row (portid, ISO3, continent, lat/lon). When a lane carries no
region column, we derive a coarse shipping basin from the resolved port's
continent + lon/lat so routing still works.

Coverage is reported, never hidden: every lane records how it matched and a routing
confidence, and the exposure summary states "X of N lanes modeled".
"""

from __future__ import annotations

import re

import duckdb


def _norm_locode(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def _norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def derive_region(continent: str, lat: float, lon: float) -> str | None:
    """Coarse shipping basin from continent + position (fallback when a CSV has no
    region column). Vocabulary matches the routing model's region keys."""
    if lat is None or lon is None:
        return None
    c = continent or ""
    if "Asia" in c:
        if 45 <= lon <= 60 and 20 <= lat <= 32:
            return "Gulf"
        if lon >= 118 and lat >= 18:
            return "East Asia"
        if 95 <= lon < 118 and lat < 20:
            return "Southeast Asia"
        if 60 <= lon < 95:
            return "South Asia"
        if lon >= 118:
            return "East Asia"
        return "Southeast Asia"
    if "Europe" in c:
        if lat >= 51 and -10 <= lon <= 15:
            return "North Europe"
        if 27 <= lat <= 47 and -6 <= lon <= 37:
            return "Mediterranean"
        if lat >= 53 and lon > 15:
            return "Baltic"
        if 40 <= lat <= 48 and 27 <= lon <= 42:
            return "Black Sea"
        return "North Europe"
    if "North America" in c:
        return "North America West" if lon <= -100 else "North America East"
    return None


class PortResolver:
    def __init__(self, con: duckdb.DuckDBPyConnection):
        rows = con.execute(
            "SELECT portid, portname, fullname, iso3, continent, lat, lon, locode FROM dim_port"
        ).fetchall()
        self._by_id: dict[str, dict] = {}
        self._by_locode: dict[str, dict] = {}
        self._by_name: dict[str, dict] = {}
        for portid, portname, fullname, iso3, continent, lat, lon, locode in rows:
            rec = {"portid": portid, "name": portname or fullname, "iso3": iso3,
                   "continent": continent, "lat": lat, "lon": lon, "locode": locode}
            self._by_id[portid] = rec
            if locode:
                self._by_locode.setdefault(_norm_locode(locode), rec)
            for nm in (portname, fullname):
                if nm:
                    self._by_name.setdefault(_norm_name(nm), rec)

    def resolve(self, token: str) -> tuple[dict | None, str | None]:
        """Return (canonical_port, matched_by) or (None, None)."""
        if not token:
            return None, None
        if token in self._by_id:
            return self._by_id[token], "portid"
        lc = _norm_locode(token)
        if lc in self._by_locode:
            return self._by_locode[lc], "locode"
        nm = _norm_name(token)
        if nm in self._by_name:
            return self._by_name[nm], "name"
        return None, None

    def region_for(self, token: str, given_region: str | None) -> tuple[str | None, dict | None, str | None]:
        """Best region for a port: prefer the CSV's region, else derive from geo."""
        rec, matched_by = self.resolve(token)
        if given_region and given_region.strip():
            return given_region.strip(), rec, matched_by
        if rec:
            return derive_region(rec.get("continent"), rec.get("lat"), rec.get("lon")), rec, matched_by
        return None, None, None
