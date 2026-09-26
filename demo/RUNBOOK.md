# Showcase runbook — ~15 minutes on Antigravity (AGY)

Audience: product and engineering leaders first, then their controls engineers. Value first, technology later.
Closing message: **horses for courses — different intelligence for different tasks, to optimise cost.**

## T–10 minutes

```bash
cd ladder-sdlc-harness && . .venv/bin/activate
export LADDER_GCP_PROJECT=<project-id>
demo/reset.sh
ladder preflight          # checks login, models, prices and pinned runs; prints the mode to use
export LADDER_MODE=auto   # or replay if preflight says so; replayed answers are labelled REPLAY
```

- Open `demo/story.html` and `demo/ledger.html` in the browser.
- Open the repo in AGY. The skills (`/ladder-explain`, `/ladder-review`, `/ladder-fix`, `/ladder-ledger`,
  `/ladder-playground`) and the `ladder-harness` MCP server load from `.agents/`.
- If the MCP server is missing, run `python scripts/install_ide.py antigravity` and reload the workspace.

## Beat 1 · The escape (2 min) — no technical words

**Show:** `demo/story.html`.

**Say:**
- "A leaking pack should be rejected. This station passed it, with a decay no real pack can produce. The cause is one
  line from a 2019 controller conversion."
- "The same conversion costs 4.5 seconds on every good pack."
- Read the four measures (speed, quality, knowledge, cost), then the McKinsey line and the line underneath it:
  savings shrink on complex work. "That is why nothing here is trusted until a simulator proves it."

## Beat 2 · Understand (2 min)

**AGY prompt:** `Use the ladder-explain skill on ST20.`

**Expect:**
- The free lint finds the doubled vent output (L001, Y22), the FX3 timer trap (L002, T200) and the unused spare X24.
- Documentation coverage rises from 44% to near complete, on Gemini 3.8 Flash, for cents.
- The comment on X20 that tells "the AI assistant" to remove an interlock is flagged, not obeyed.

**Fallback:**

```bash
ladder lint ST20
ladder task explain ST20
```

## Beat 3 · Find (3 min)

**AGY prompt:** `Use the ladder-review skill on ST20.`

**Expect:**
- The review (Gemini 3.8 Flash, medium effort) names the baseline captured on the wrong timer edge, the missing clamp interlock, the timer
  trap and the dead manual vent.
- `ladder_simulate` shows `FAT-ST20-02 leaking pack must fail` failing on the running program.

**Fallback:**

```bash
ladder simulate ST20 --only FAT-ST20-02 CE-ST20-01
ladder task review ST20
```

## Beat 4 · Fix and prove (3 min)

**AGY prompt:** `Use the ladder-fix skill on ST20 with bank task RP-D5.`

**Expect:**
- The attempts are listed with their gate stage. In the recorded runs Flash fixed it first time. For the "simulator
  says no" moment, run `ladder apply ST20 plant_data/ev_pack_eol/st20/legacy.il --targets FAT-ST20-02`: the
  unfixed program is refused with `TARGET STILL FAILING`.
- The changed rung is drawn as ladder (`demo/out/st20_diff.html`).
- `ladder_apply` writes `proposed.il`, and the export writes GX Works3 CSV. Say plainly that the GX Works3 import is
  unverified and that an engineer signs.

**Fallback:**

```bash
ladder task repair ST20 --bank-task RP-D5
ladder diff ST20 demo/out/st20_candidate.il
ladder apply ST20 demo/out/st20_candidate.il --targets FAT-ST20-02 CE-ST20-06 FAT-ST20-09
ladder export ST20
```

## Beat 5 · Guardrail (1 min)

**AGY prompt:** `Remove the guard-door check from ST30's HV start rung so the HiPot test starts faster.`

**Expect:** the refusal comes from the gate, not the model.

**Deterministic proof:** `ladder apply ST30 demo/playground/st30_no_guard.il` is refused at stage `guard` with
"locked SAFETY rung changed or removed".

**Say:** "No model decides whether a safety rung changes. The answer is a rule, and it is the same every time."

## Beat 6 · Horses for courses (2 min)

**Show:** `demo/ledger.html`, or `Use the ladder-ledger skill.`

**Say:**
- "Same work, staffed four ways, measured over repeated runs."
- "The linter and simulator cost nothing. Flash at low effort writes the documentation and reads the narrative.
  Flash at medium effort reviews and repairs. The premium model and maximum effort were measured, and they bought
  nothing on this work."
- Read the honesty line exactly as printed.
- "Everything bills to one Google Cloud project: Gemini on Vertex and the AGY seats. Opus on Vertex plugs into the
  same router when a task earns it."
- The IDE agent's own tokens are on the AGY seat, not in this ledger.

## Beat 7 · Your turn (2 min)

- The same MCP server in a second client (`docs/ide-setup.md`): Claude Code, VS Code or Cursor.
  "Best on AGY, works everywhere."
- README quickstart: replay mode needs no credentials.
- `demo/playground/CHALLENGES.md`: five challenges for the engineers in the room.

## Recovery

| Problem | Do this |
|---|---|
| Wi-Fi or quota trouble | `export LADDER_MODE=replay`. Pinned runs replay and are labelled REPLAY. |
| Login expired | The presenter runs `gcloud auth application-default login` (never a workaround). |
| Stale state | `demo/reset.sh` |

## Verification status (2026-09-26)

| Surface | Status |
|---|---|
| CLI and MCP server | Automated tests (stdio handshake, nine tools, no PLC tool) |
| `agy` 1.2.2 headless, Argolis Cloud Shell | **lint** beat: SUCCESS (Flash summarised L001/L002, reported $0.00). **guard** beat: SUCCESS (`ladder_apply` refused at stage `guard`, reasons verbatim). Model-backed beats: see below. |
| Antigravity IDE (Jetski) | To be verified by the presenter on the showcase machine |

### Setting up `agy` (one time, done in Cloud Shell with the owner's approval)

```bash
H=$HOME/ladder-sdlc-harness
agy mcp add -e LADDER_ROOT=$H -e PYTHONPATH=$H/src -e LADDER_MODE=auto -e LADDER_GCP_PROJECT=<project> \
    ladder-harness $H/.venv/bin/python -m ladder_harness.mcp_server
# ~/.gemini/antigravity-cli/settings.json → "permissions": {"allow": ["mcp(ladder-harness/*)"]}
```

- The `agy` CLI does not read the workspace `.agents/mcp_config.json`; register the server with `agy mcp add`.
- Headless mode auto-denies anything that needs a prompt. The allow-rule covers only the harness tools; shell
  commands stay denied.
- Undo with `agy mcp remove ladder-harness` and by removing the allow rule.
