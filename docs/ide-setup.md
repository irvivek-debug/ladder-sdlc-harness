# Use the harness from any IDE

The harness is one stdio MCP server (`ladder-harness`), plus a CLI and an `AGENTS.md`. Any IDE whose agent speaks
MCP gets the same nine tools.

## 1. Install (once)

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[ai,mcp,dev]"          # add ,evals to run the evaluation suite
```

This gives you `ladder` (CLI) and `ladder-mcp` (server) on your PATH while the venv is active.

## 2. Credentials (live models only)

Replay mode needs nothing. Live calls to Gemini and Claude on Google Cloud use your own login:

```bash
gcloud auth application-default login
export LADDER_GCP_PROJECT=<your-project-id>
```

Claude Opus 5.5 must be enabled for the project in Model Garden. The harness never uses key files.

## 3. Wire up your IDE

`python scripts/install_ide.py <ide…>` writes a config with absolute paths, so the server starts whichever shell or
directory the IDE uses. Those files are gitignored because they contain your paths.

| IDE | Command | File written | Notes |
|---|---|---|---|
| Google Antigravity (IDE and `agy` CLI) | `python scripts/install_ide.py antigravity` | `.agents/mcp_config.json` | Also reads `AGENTS.md`, `.agents/rules/` and the skills in `.agents/skills/` (`/ladder-explain`, `/ladder-review`, `/ladder-fix`, `/ladder-ledger`, `/ladder-playground`). |
| Claude Code | `python scripts/install_ide.py claude` | `.mcp.json` | Approve the server when prompted. |
| VS Code (Copilot agent) | `python scripts/install_ide.py vscode` | `.vscode/mcp.json` | |
| Cursor | `python scripts/install_ide.py cursor` | `.cursor/mcp.json` | |
| JetBrains AI Assistant | — | — | Add a stdio MCP server in Settings → Tools → AI Assistant → MCP, using the command and env that `--print claude` shows. |

Templates without absolute paths are in `docs/ide-configs/`.

## 4. Try it

- `ladder lint ST20` — free findings in about a second.
- `ladder simulate ST20` — factory-acceptance and C&E scenarios on the FX5 simulator.
- `LADDER_MODE=replay ladder task review ST20` — the recorded Opus review, no credentials needed.
- In the IDE agent: *"Use the ladder-review skill on ST20."*

## Verification status

| Surface | Status |
|---|---|
| MCP stdio handshake + tool list | Automated test (`tests/test_surfaces.py`) |
| Claude Code | Verified on the author's machine |
| `agy` CLI (Antigravity) in Cloud Shell | See `demo/RUNBOOK.md` |
| Antigravity IDE, VS Code, Cursor, JetBrains | Configuration documented; to be verified by the presenter |
