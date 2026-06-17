"""Migration gate: the contracts DERIVED from the shape registry equal the hand literals.

``registry/shapes.py`` is the new single source of truth; ``contracts.SIDECAR_CONTRACTS``
is derived from it. This test pins the derived dict against the EXACT literals that lived
in contracts.py before the migration (captured here verbatim), so the refactor is proven
to have changed no contract — and the three H1-F additions (signals_fdr / timeseries /
stress) are asserted to exist and to be CORE.
"""

from __future__ import annotations

from freight_radar.contracts import CORE_STEMS, SIDECAR_CONTRACTS, Contract

# --- the contract literals exactly as they stood before the shapes migration -----------
# (captured from the pre-migration contracts.py so the derivation is proven equal.)
_OLD_LITERALS: dict[str, Contract] = {
    "snapshot": Contract(
        requires=frozenset({"generated_at", "as_of", "chokepoints", "ports", "source"}),
        nonempty_lists=frozenset({"chokepoints", "ports"}),
    ),
    "lanes": Contract(
        is_array=True,
        item_requires=frozenset({"from", "to", "intensity"}),
        min_items=1,
    ),
    "flags": Contract(
        is_array=True,
        item_requires=frozenset({"flag_id", "portid", "entity", "severity"}),
        min_items=0,
    ),
    "quakes": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"id", "mag", "lat", "lon", "place", "url"}),
        min_items=1,
    ),
    "news_geo": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"category", "lat", "lon", "url"}),
        min_items=1,
    ),
    "eonet": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"id", "title", "category", "lat", "lon", "url"}),
        min_items=1,
    ),
    "marine": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"name", "lat", "lon", "wave_height_m", "observed_at"}),
        min_items=1,
    ),
    "tides": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"port", "lat", "lon", "water_level_ft", "observed_at", "url"}),
        min_items=1,
    ),
    "streamflow": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "items"}),
        items_key="items",
        item_requires=frozenset({"site", "river", "lat", "lon", "stage_ft", "url"}),
        min_items=1,
    ),
    "disruptions": Contract(
        requires=frozenset({"generated_at", "source", "source_url", "events"}),
        items_key="events",
        item_requires=frozenset({"eventid", "type", "alertlevel", "lat", "lon", "name"}),
        min_items=0,
    ),
    "gatun": Contract(
        requires=frozenset(
            {"generated_at", "as_of", "available", "current_level_ft", "lat", "lon", "projection"}
        ),
    ),
}
# the six FRED-z signal families shared one literal contract.
_OLD_SIGNAL = Contract(
    requires=frozenset({"generated_at", "source", "source_url", "method", "items", "counts"}),
    items_key="items",
    item_requires=frozenset({"id", "name", "our_zscore", "fdr_significant"}),
    min_items=1,
)
for _sig in ("commodities", "macro", "metals", "freight_rate", "slack", "labor"):
    _OLD_LITERALS[_sig] = _OLD_SIGNAL


def test_derived_contracts_equal_old_literals():
    """Every stem that was hand-contracted still derives to the IDENTICAL Contract."""
    for stem, old in _OLD_LITERALS.items():
        assert stem in SIDECAR_CONTRACTS, f"{stem} dropped from SIDECAR_CONTRACTS"
        assert SIDECAR_CONTRACTS[stem] == old, f"derived contract for {stem} drifted from the old literal"


def test_h1f_additions_present():
    """H1-F: the three previously-uncontracted measured sidecars now have contracts."""
    for stem in ("signals_fdr", "timeseries", "stress"):
        assert stem in SIDECAR_CONTRACTS, f"{stem} must be contracted (H1-F)"


def test_signals_fdr_floor():
    """signals_fdr is the POOLED artifact — its floor is method/counts/items + the per-row z."""
    c = SIDECAR_CONTRACTS["signals_fdr"]
    assert c.requires == frozenset({"counts", "items", "method"})
    assert c.items_key == "items"
    assert c.item_requires == frozenset({"id", "our_zscore", "fdr_significant"})
    assert c.min_items == 1


def test_core_stems_include_stress_and_timeseries():
    """H1-F remnant: stress + timeseries join the measured spine the publish blocks on."""
    assert {"snapshot", "lanes", "flags", "stress", "timeseries"} <= CORE_STEMS
