"""P6 capstone — the DERIVED briefing is grounded, association-only, and admissible.

The reasoner is offline (Claude Code), but its output is gated in CI like everything else:
every claim cites a real layer, carries no causal/forecast verb, and owns no number. (The
quarantine — derived/ can't reach the fact path, and nothing imports derived/ — is proven in
test_layer_firewall.)
"""

from __future__ import annotations

from pathlib import Path

from freight_radar.derived.briefing import load, scan_rendered, validate
from freight_radar.registry.layers import REGISTRY, Kind, by_id

BRIEFING = Path(__file__).resolve().parents[2] / "frontend" / "public" / "data" / "ai_briefing.json"
VALID_IDS = {d.id for d in REGISTRY}


def test_ai_briefing_is_a_registered_derived_layer() -> None:
    d = by_id("ai_briefing")
    assert d.kind is Kind.DERIVED
    assert d.metric is None  # DERIVED owns no number, by construction


def test_committed_briefing_passes_the_honesty_gates() -> None:
    violations = validate(load(BRIEFING), VALID_IDS)
    assert violations == [], violations


def test_every_claim_cites_a_real_layer() -> None:
    briefing = load(BRIEFING)
    assert briefing["tier"] == "DERIVED" and briefing["claims"]
    for c in briefing["claims"]:
        assert c["cites"], "every claim must trace to the store"
        assert all(cite in VALID_IDS for cite in c["cites"]), c


def test_validate_rejects_ungrounded_causal_or_metric_claims() -> None:
    base = {"tier": "DERIVED", "agent_model": "claude", "claims": []}
    valid = {"stress"}
    assert validate({**base, "claims": [{"text": "x", "cites": []}]}, valid)  # zero cites
    assert validate({**base, "claims": [{"text": "x", "cites": ["nope"]}]}, valid)  # bad cite
    assert validate(  # causal verb
        {**base, "claims": [{"text": "the drop was caused by the quake", "cites": ["stress"]}]},
        valid,
    )
    assert validate({**base, "metric": 5, "claims": [{"text": "x", "cites": ["stress"]}]}, valid)
    assert validate({"tier": "SPINE", "agent_model": "c", "claims": [{"text": "x", "cites": ["stress"]}]}, valid)
    # a clean briefing passes
    assert (
        validate(
            {**base, "claims": [{"text": "stress reads 41.6", "cites": ["stress"]}]},
            valid,
        )
        == []
    )


def test_rendered_firewall_catches_drift_in_any_agent_field() -> None:
    """The rendered firewall is FAIL-CLOSED: causal/forecast language in a NEW agent-authored
    field (a summary/headline the structured claim-check never looks at) still fails. This is
    the 5-year plan's 'amid escalating' guard — erosion that wouldn't trip the schema."""
    clean = {
        "tier": "DERIVED",
        "agent_model": "claude",
        "claims": [{"text": "stress reads 41.6", "cites": ["stress"]}],
    }
    assert scan_rendered(clean) == []
    # a brand-new free-text field with directional drift is caught even though it's not a claim
    assert scan_rendered({**clean, "summary": "the chain is worsening amid escalating tension"})
    assert scan_rendered({**clean, "headline": "a spike in disruptions"})
    # but the fixed boilerplate that legitimately negates the words is NOT a false positive
    assert (
        scan_rendered(
            {**clean, "method": "the agent never forecasts", "disclaimer": "never causation"}
        )
        == []
    )


# --- the synthesis step: connecting a measured fact to its co-occurring cited news ---

from freight_radar.derived.gate import attribution_violations  # noqa: E402
from freight_radar.derived.reason import _clean_source, _connections  # noqa: E402
from freight_radar.honesty.lexicon import scan as scan_causal  # noqa: E402

DATA_DIR = BRIEFING.parent


def test_clean_source_rejects_digits_and_causal_tokens() -> None:
    # a digit in a source name would break the attribution gate; a causal/forecast token, the firewall
    assert _clean_source("NPR") == "NPR"
    assert _clean_source("Channel 4 News") is None
    assert _clean_source("Forecast Daily") is None
    assert _clean_source("   ") is None


def test_connections_join_a_measured_pct_to_cited_news_as_association_only() -> None:
    flags = [
        {"flag_id": "f1", "entity": "Strait of Hormuz", "kind": "chokepoint_persistent_collapse",
         "pct_change": -92.4, "severity": 83},
        {"flag_id": "f2", "entity": "Quietport", "kind": "port_activity_drop",
         "pct_change": -5.0, "severity": 5},  # no news entry -> must be skipped
    ]
    news = {"items": {"f1": {"entity": "Strait of Hormuz", "items": [
        {"source": "NPR"}, {"source": "CNBC"}, {"source": "The New York Times"}, {"source": "NBC News"}]}}}
    conns = _connections(flags, news, k=3)
    assert len(conns) == 1, "only the flag with co-occurring news is connected"
    text, cites = conns[0]
    assert cites == ["flags", "news"]               # the pct is from flags, the count from news
    assert "-92.4%" in text and "4 cited news reports" in text
    assert "never a stated cause" in text
    assert scan_causal(text) == []                  # association-only: no causal/forecast verb


def test_committed_briefing_connection_numbers_stay_entailed() -> None:
    # the full attribution gate over the real artifact: EVERY number (incl. the connection claims')
    # is verbatim-entailed by a cited layer, or this fails. Guards the synthesis in CI, fail-closed.
    assert attribution_violations(load(BRIEFING), out_dir=DATA_DIR) == []
    # and at least one connection actually shipped (flags+news cite pair)
    claims = load(BRIEFING)["claims"]
    assert any(set(c["cites"]) == {"flags", "news"} for c in claims), "expected >=1 fact<->news connection"
