"""The Standpoint Knowledge MCP server — read-only store access for agents (P1.5).

Run (stdio):  cd backend && uv run --extra mcp python -m freight_radar.mcp.server

Exposes list_layers / get_layer_facts / nearby — every result is facts-with-provenance
from the published store. There is NO write tool: an agent can read + cite the whole
tier-stamped store, never mutate it. This is the honesty firewall extended to the agent
interface (STANDPOINT-VISION.md §4): the same boundary that stops a CONTEXT layer from
writing a fact stops the reasoner from inventing one. The *reasoner itself* stays P6 —
this is the read lens only.
"""

from __future__ import annotations

from .tools import TOOLS, assert_read_only


def build_server():
    """Build (but don't run) the FastMCP server — also the import-time no-write assertion."""
    from mcp.server.fastmcp import FastMCP

    assert_read_only()  # refuse to build a server that exposes a mutator
    mcp = FastMCP("standpoint-knowledge")
    for spec in TOOLS:
        mcp.add_tool(spec.handler, name=spec.name, description=spec.description)
    return mcp


def main() -> None:
    build_server().run()  # stdio transport


if __name__ == "__main__":
    main()
