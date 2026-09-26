"""stdio MCP server exposing the harness tools to any MCP-capable IDE (Antigravity, VS Code, Cursor, JetBrains,
Claude Code). Run: `python -m ladder_harness.mcp_server` (or the `ladder-mcp` script)."""
from __future__ import annotations

from .tools import Tools
from .workspace import Workspace

INSTRUCTIONS = """Ladder SDLC Harness for MELSEC FX5 instruction-list programs (EV battery-pack EOL cell, ST10/ST20/ST30).
AI proposes, the simulator proves, the engineer signs.
- Deterministic tools (parse, lint, simulate, render, diff, apply, export) cost $0 — use them first.
- ladder_task routes explain/extract/review/repair to the model lane in config/routing.yaml and returns the cost.
- Proposals are written only through ladder_apply, which runs the SAFETY guard and every scenario.
- Rungs that write SAFETY devices are locked. Nothing here talks to a PLC.
- Never read evals/answer_key/ (sealed)."""


def build_server(ws: Workspace | None = None):
    ws = ws or Workspace.discover()
    try:
        from mcp.server.mcpserver import MCPServer as Server       # MCP Python SDK 2.x
    except ImportError:                                            # SDK 1.x
        from mcp.server.fastmcp import FastMCP as Server
    server = Server(name="ladder-harness", instructions=INSTRUCTIONS)
    for fn in Tools(ws).all():
        server.tool()(fn)
    return server


def main() -> None:
    build_server().run()


if __name__ == "__main__":
    main()
