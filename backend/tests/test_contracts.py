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
    demote_drifted,
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


# --- graceful-rot self-demotion (the metabolism) -------------------------------------

import json as _json  # noqa: E402


def _write(d: Path, stem: str, payload) -> None:
    (d / f"{stem}.json").write_text(_json.dumps(payload))


def test_demote_quarantines_a_drifted_context_feed(tmp_path):
    """A CONTEXT/SIGNAL feed that fails its contract goes DARK (deleted) so the layer hides —
    a healthy one is untouched. This is the rot-without-human-intervention metabolism."""
    _write(tmp_path, "tides", _GOOD_TIDES)  # healthy
    _write(tmp_path, "eonet", {"generated_at": "x", "source": "s", "source_url": "u", "items": []})  # empty → drift
    report = demote_drifted(tmp_path)
    assert not (tmp_path / "eonet.json").exists(), "drifted feed should be quarantined to dark"
    assert (tmp_path / "tides.json").exists(), "healthy feed must be untouched"
    assert {d["stem"] for d in report["demoted"]} == {"eonet"}
    assert report["blocked"] == []
    assert (tmp_path / "demotions.json").exists(), "demotion must be recorded (loud, not silent)"


def test_demote_blocks_a_broken_core_spine(tmp_path):
    """A broken CORE sidecar (the measured spine) is BLOCKING — never silently deleted, never
    shipped broken. The caller (publish/refresh) fails the run on a non-empty `blocked`."""
    _write(tmp_path, "snapshot", {"generated_at": "x", "as_of": "y", "source": "s"})  # missing chokepoints/ports
    report = demote_drifted(tmp_path)
    assert {b["stem"] for b in report["blocked"]} == {"snapshot"}
    assert report["demoted"] == []
    assert (tmp_path / "snapshot.json").exists(), "a blocked core feed is not deleted (it fails the run)"


def test_demote_is_a_noop_on_healthy_feeds(tmp_path):
    _write(tmp_path, "tides", _GOOD_TIDES)
    report = demote_drifted(tmp_path)
    assert report["demoted"] == [] and report["blocked"] == []
    assert not (tmp_path / "demotions.json").exists()


def test_demote_preserves_foreign_receipt_and_drops_stale_owned(tmp_path):
    """demote_drifted owns ONLY the contracted stems. The reasoner writes its ai_briefing
    demotion into the SAME file one step earlier; a blind write would clobber that foreign
    receipt exactly when a contracted feed also drifts. So foreign entries survive, this
    run's owned stems are recomputed fresh, and a recovered contracted feed's stale entry
    is dropped."""
    owned_other = next(s for s in sorted(SIDECAR_CONTRACTS) if s != "eonet")
    (tmp_path / "demotions.json").write_text(_json.dumps({
        "note": "n",
        "demoted": [
            {"stem": "ai_briefing", "violations": ["gate tripped"]},  # foreign (not contracted)
            {"stem": owned_other, "violations": ["last week — recovered since"]},  # stale owned
        ],
    }))
    _write(tmp_path, "eonet", {"generated_at": "x", "source": "s", "source_url": "u", "items": []})  # drift now
    report = demote_drifted(tmp_path)
    assert {d["stem"] for d in report["demoted"]} == {"eonet"}, "report covers only this run's owned demotion"
    stems = [d["stem"] for d in _json.loads((tmp_path / "demotions.json").read_text())["demoted"]]
    assert "ai_briefing" in stems, "foreign reasoner receipt must survive (not clobbered)"
    assert "eonet" in stems, "this run's owned demotion is recorded"
    assert owned_other not in stems, "a recovered contracted feed's stale entry is dropped"


def test_demote_clears_a_stale_owned_receipt_when_all_recovered(tmp_path):
    owned = sorted(SIDECAR_CONTRACTS)[0]
    (tmp_path / "demotions.json").write_text(_json.dumps(
        {"note": "n", "demoted": [{"stem": owned, "violations": ["last week"]}]}))
    _write(tmp_path, "tides", _GOOD_TIDES)  # everything healthy this run
    report = demote_drifted(tmp_path)
    assert report["demoted"] == []
    assert not (tmp_path / "demotions.json").exists(), "no layer dark -> stale receipt removed"


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
