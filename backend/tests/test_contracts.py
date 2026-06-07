"""Non-live CI gate for the upstream-drift detector.

Validates the *committed* sidecars in ``frontend/public/data`` against the declared data
contracts. A producer whose output silently changes shape — drops a geo key the globe
reads, renames its items array, returns an empty feed — fails here, in review, instead of
shipping a quietly-degraded map. The live half (a fresh-fetch check) runs in refresh.yml.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from freight_radar.contracts import (
    SIDECAR_CONTRACTS,
    check_payload,
    check_dir,
)

# repo-root/frontend/public/data — the committed sidecars the live site serves
DATA_DIR = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data"


@pytest.mark.parametrize("stem", sorted(SIDECAR_CONTRACTS))
def test_committed_sidecar_conforms(stem: str):
    """Every contracted sidecar that is committed must satisfy its contract."""
    path = DATA_DIR / f"{stem}.json"
    if not path.exists():
        pytest.skip(f"{stem}.json not committed in this checkout")
    payload = json.loads(path.read_text())
    violations = check_payload(stem, payload)
    assert not violations, "contract drift:\n  " + "\n  ".join(violations)


def test_core_sidecars_present():
    """The measured spine the app blocks on must always be present + conformant."""
    _, missing = check_dir(DATA_DIR)
    core = {"snapshot", "lanes", "flags"}
    assert not (core & set(missing)), f"core sidecars absent: {sorted(core & set(missing))}"


def test_contract_check_is_clean_on_committed_data():
    """The full committed data dir carries no schema/liveness drift (the receipt)."""
    violations, _ = check_dir(DATA_DIR)
    assert not violations, f"drift in committed sidecars: {violations}"


def test_unknown_stem_is_noop():
    """A sidecar with no contract is not an error — coverage is opt-in, never silent-fail."""
    assert check_payload("definitely_not_a_layer", {"anything": 1}) == []


# --- the detector's teeth: it must FIRE on each real drift mode ------------------------

_GOOD_TIDES = {
    "generated_at": "x",
    "source": "NOAA",
    "source_url": "u",
    "items": [
        {"port": "X", "lat": 1.0, "lon": 2.0, "water_level_ft": 3.0, "observed_at": "t", "url": "u"}
    ],
}


def test_detects_missing_top_key():
    bad = {k: v for k, v in _GOOD_TIDES.items() if k != "source"}
    assert any("missing top-level key 'source'" in m for m in check_payload("tides", bad))


def test_detects_renamed_items_array():
    bad = {**_GOOD_TIDES}
    bad["rows"] = bad.pop("items")  # upstream renamed the array
    msgs = check_payload("tides", bad)
    assert any("items key 'items' is missing" in m for m in msgs)


def test_detects_missing_item_key():
    bad = {**_GOOD_TIDES, "items": [{"port": "X", "lat": 1.0, "lon": 2.0}]}  # dropped water_level_ft
    assert any("item(s) missing key 'water_level_ft'" in m for m in check_payload("tides", bad))


def test_detects_empty_feed():
    bad = {**_GOOD_TIDES, "items": []}  # feed went empty (min_items=1)
    assert any("expected >= 1" in m for m in check_payload("tides", bad))


def test_detects_wrong_top_type():
    assert check_payload("tides", [1, 2, 3])  # object expected, got array


def test_detects_array_sidecar_drift():
    """An array sidecar (lanes) flags a non-array payload and missing item keys."""
    assert check_payload("lanes", {"not": "an array"})
    assert any(
        "missing key 'intensity'" in m
        for m in check_payload("lanes", [{"from": [0, 0], "to": [1, 1]}])
    )


def test_clean_payload_has_no_violations():
    assert check_payload("tides", _GOOD_TIDES) == []


def test_catalog_surfaces_contract_monitored():
    """The agent-legible catalog marks each output layer whose feed shape is monitored, so
    the Source Ledger (and an agent) can see which feeds are drift-checked."""
    from freight_radar.store import catalog

    layers = catalog()["layers"]
    by_id = {layer["id"]: layer for layer in layers}
    # every catalog layer carries the boolean
    assert all("contract_monitored" in layer for layer in layers)
    # a contracted external feed is flagged; an uncontracted/derived one is not
    assert by_id["tides"]["contract_monitored"] is True
    assert by_id["marine"]["contract_monitored"] is True
    monitored = {layer["id"] for layer in layers if layer["contract_monitored"]}
    assert monitored, "expected some monitored layers in the catalog"
