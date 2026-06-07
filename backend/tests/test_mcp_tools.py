"""P1.5 — the MCP tool contract is read-only + provenance-returning.

Tests the contract WITHOUT the MCP SDK (mcp/tools.py has no SDK dep), so CI proves the
agent interface exposes only read tools — the AI firewall — without installing the SDK.
The server wiring (server.py) is verified separately with `--extra mcp`.
"""

from __future__ import annotations

from freight_radar import store
from freight_radar.mcp import tools


def test_exactly_the_three_read_tools() -> None:
    assert {t.name for t in tools.TOOLS} == {"list_layers", "get_layer_facts", "nearby"}


def test_all_tools_declared_read_only() -> None:
    tools.assert_read_only()  # raises if any tool is a mutator


def test_no_tool_name_is_a_mutator() -> None:
    for t in tools.TOOLS:
        bad = [m for m in tools.WRITE_TOOL_MARKERS if m in t.name.lower()]
        assert not bad, f"{t.name} looks like a mutator: {bad}"


def test_every_tool_has_a_docstring_description() -> None:
    for t in tools.TOOLS:
        assert t.description.strip(), f"{t.name} has no description (agents need it)"


def test_list_layers_returns_tier_stamped_catalog() -> None:
    cat = tools.list_layers()
    assert cat["counts"]["layers"] >= 20
    assert set(cat["counts"]["by_tier"]) == {"SPINE", "SIGNAL", "CONTEXT", "DERIVED"}


def test_get_layer_facts_carries_provenance() -> None:
    got = tools.get_layer_facts("stress")
    assert got["kind"] == "SPINE"
    assert "source" in got and "honesty_note" in got  # provenance shape always present


def test_nearby_tool_is_association_only_and_distance_ordered() -> None:
    r = tools.nearby(26.5, 56.2, 900.0)
    assert r["disclaimer"] == store.ASSOCIATION_ONLY
    kms = [i["km"] for i in r["items"]]
    assert kms == sorted(kms)  # distance only, never a severity/evidence ranking
