"""Phase B — national-dependence weighting + brief note (deterministic, no network).

Verifies the two systemic-importance behaviours: a sole-gateway port outranks an
equally-busy port that is one of many in its country, and a flagged systemic port
gets a cited national-dependence line in its brief (while a minor port gets none).
"""

from __future__ import annotations

import pandas as pd

from freight_radar.detect.run_detection import _econ_weights, _national_dependence_note


def test_national_share_lifts_a_sole_gateway_over_an_equal_sized_peer():
    vc = pd.Series({"sole": 1000.0, "minor": 1000.0})  # identical global size
    nat = pd.Series({"sole": 99.0, "minor": 3.0})       # very different national reliance
    w = _econ_weights(vc, national_share=nat)
    assert w["sole"] > w["minor"], "the country's sole gateway must weigh more"
    # without the national signal, equal vessel counts weigh equally (back-compat)
    w0 = _econ_weights(vc)
    assert w0["sole"] == w0["minor"]


def test_weights_stay_in_band():
    vc = pd.Series({"a": 10.0, "b": 5000.0, "c": 200.0})
    nat = pd.Series({"a": 100.0, "b": 1.0, "c": 50.0})
    for w in _econ_weights(vc, national_share=nat).values():
        assert 0.6 <= w <= 1.0


def test_dependence_note_present_for_systemic_port_and_absent_for_minor():
    high = pd.Series({
        "share_country_maritime_import": 99.8,
        "share_country_maritime_export": 97.5,
        "country": "Kenya",
    })
    note = _national_dependence_note(high, "Mombasa")
    assert "Kenya" in note and "%" in note
    assert "single-port dependency" in note.lower()  # >= 80% triggers the sole-port phrasing

    low = pd.Series({
        "share_country_maritime_import": 3.0,
        "share_country_maritime_export": 2.0,
        "country": "United States",
    })
    assert _national_dependence_note(low, "Minor Terminal") == ""
