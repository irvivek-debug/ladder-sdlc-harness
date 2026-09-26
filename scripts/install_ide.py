#!/usr/bin/env python3
"""Write MCP configs for your IDEs with absolute paths to this checkout's Python, so the server starts no matter
which directory or shell the IDE uses. Run it yourself; it only writes the files you name.

    python scripts/install_ide.py antigravity claude vscode cursor      # any subset
    python scripts/install_ide.py --print claude                        # show, don't write
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = {
    "antigravity": (ROOT / ".agents" / "mcp_config.json", "mcpServers"),
    "claude": (ROOT / ".mcp.json", "mcpServers"),
    "cursor": (ROOT / ".cursor" / "mcp.json", "mcpServers"),
    "vscode": (ROOT / ".vscode" / "mcp.json", "servers"),
}


def server_entry(kind: str) -> dict:
    entry = {"command": sys.executable, "args": ["-m", "ladder_harness.mcp_server"],
             "env": {"LADDER_ROOT": str(ROOT), "PYTHONPATH": str(ROOT / "src"), "LADDER_MODE": "auto"}}
    return {"type": "stdio", **entry} if kind == "servers" else entry


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("ides", nargs="+", choices=sorted(TARGETS))
    ap.add_argument("--print", action="store_true", help="print the config instead of writing it")
    args = ap.parse_args()
    for ide in args.ides:
        path, key = TARGETS[ide]
        doc = json.loads(path.read_text()) if path.exists() else {}
        doc.setdefault(key, {})["ladder-harness"] = server_entry(key)
        text = json.dumps(doc, indent=2) + "\n"
        if args.print:
            print(f"# {path}\n{text}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            print(f"wrote {path.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
