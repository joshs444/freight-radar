"""The read-only tool contract for the Standpoint Knowledge MCP server.

This module has NO MCP-SDK dependency on purpose: the tool CONTRACT (names, the
read-only flag, the handlers) is plain Python, so CI can prove the server exposes only
read tools without installing the SDK. ``server.py`` wires these into a FastMCP server.

Every tool returns facts-with-provenance from :mod:`freight_radar.store` (the read
surface) and is read-only by construction — there is no tool that writes, ingests, or
mutates the store. That is the AI firewall: an agent can read the whole tier-stamped
store and cite it, but can never make it say something it didn't compute.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .. import store


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    handler: Callable
    read_only: bool = True


def list_layers() -> dict:
    """List every layer in the Standpoint store with its tier (SPINE measured / SIGNAL
    measured / CONTEXT cited), the statistic it owns (if any), its cited source, and where
    its data lives. Start here to learn what the store contains."""
    return store.catalog()


def get_layer_facts(layer_id: str) -> dict:
    """Get one layer's published facts, wrapped with its provenance (tier, source, method).
    `layer_id` is an id from list_layers (e.g. 'stress', 'quakes', 'gatun', 'snapshot')."""
    return store.get_layer(layer_id)


def nearby(lat: float, lon: float, radius_km: float = 750.0) -> dict:
    """Cited CONTEXT facts (news, earthquakes, storms) within `radius_km` of a point,
    ordered ONLY by distance and stamped association-only — never a stated cause, never a
    ranking by severity. Use it to see what cited context co-locates with a place."""
    return store.nearby(lat, lon, radius_km)


def verify(claim_layer: str, entity_id: str | None = None) -> dict:
    """Ground a claim before asserting it. Returns the store's cited observation for
    `claim_layer` (optionally narrowed to `entity_id`) WITH provenance, or ABSTAINS. It never
    returns a true/false verdict — if the store doesn't measure what the claim is about (a
    geopolitics narrative, a forecast), it returns result='abstain'. Call this before stating
    anything about the world and SUPPRESS the claim on abstain: the honest 'no' is the answer."""
    return store.verify(claim_layer, entity_id)


# The registered tools. ALL read-only — there is intentionally no write/ingest/mutate tool.
TOOLS: list[ToolSpec] = [
    ToolSpec("list_layers", list_layers.__doc__ or "", list_layers),
    ToolSpec("get_layer_facts", get_layer_facts.__doc__ or "", get_layer_facts),
    ToolSpec("nearby", nearby.__doc__ or "", nearby),
    ToolSpec("verify", verify.__doc__ or "", verify),
]

# Substrings that would indicate a mutation surface — must never appear in a tool name.
WRITE_TOOL_MARKERS = (
    "write",
    "set",
    "put",
    "delete",
    "update",
    "ingest",
    "mutate",
    "create",
    "publish",
    "promote",
)


def assert_read_only() -> None:
    """Raise if any tool is a mutator — the structural no-write guarantee."""
    for t in TOOLS:
        assert t.read_only, f"{t.name} is not declared read_only"
        low = t.name.lower()
        bad = [m for m in WRITE_TOOL_MARKERS if m in low]
        assert not bad, f"tool {t.name!r} looks like a mutator ({bad})"
