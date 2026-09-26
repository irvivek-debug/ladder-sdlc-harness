# Ladder SDLC Harness

**AI proposes. The simulator proves. The engineer signs.**

A working harness for the software lifecycle of MELSEC iQ-F (FX5) ladder programs, written as instruction lists:
understand, document, change, test and review. Each task runs on the model that suits it, and every change is
proven on a scan-accurate simulator before an engineer sees it.

The sample plant is an EV battery-pack end-of-line cell with three stations:

- ST10 — conveyor;
- ST20 — pressure-decay leak test;
- ST30 — HV insulation test, which is SAFETY-classified.

The cell comes with a legacy program that passes leaking packs.

## 60-second quickstart (no credentials)

```bash
git clone <this repo> && cd ladder-sdlc-harness
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[ai,mcp,dev]"
ladder lint ST20                       # free: double coil, FX3 timer trap, spare input, comment coverage
ladder simulate ST20                   # free: 22 factory and C&E scenarios on the FX5 simulator
LADDER_MODE=replay ladder task review ST20   # a recorded Opus 5.5 review, labelled REPLAY
```

## Horses for courses

| Task class | Examples | Runs on |
|---|---|---|
| T0 deterministic | parse, lint, simulate, render, diff, the apply gate | no model, $0 |
| T1 bulk | device comments, rung purposes | Gemini 3.8 Flash |
| T2 extraction | narrative to structured spec, conflicts | Gemini 3.8 Flash |
| T3 change | repair until the plant tests pass | the lane the evaluations chose |
| T4 review | code against narrative, interlocks | Claude Opus 5.5 on Vertex AI |
| T5 SAFETY | may this safety rung change? | a deterministic guard, never a model |

The lanes in `config/routing.yaml` are an **output** of the evaluation sweep: for each class, the cheapest model and
effort that is not significantly worse than the best. The exception is review, which takes the best reviewer. See
`evals/REPORT.md` for the four staffing profiles (all Opus, Opus at low effort, all Flash, routed), reported as
ranges over repeated runs.

## Use it from any IDE

One stdio MCP server (`ladder-mcp`) exposes nine tools to Antigravity, Claude Code, VS Code, Cursor and JetBrains.
`AGENTS.md` sets the rules for coding agents, and `.agents/` carries the Antigravity rules and skills. See
`docs/ide-setup.md`.

## What makes a change real

`ladder apply` runs, in order:

1. parse;
2. the SAFETY guard — locked rungs, and reads of E-stop and guard inputs, cannot be removed;
3. no new lint errors;
4. every scenario, where the targets must now pass and nothing may regress.

Only then does it write `proposed.il`, together with a GX Works3 CSV export for the engineer. Nothing in this
repository talks to a PLC.

## Evidence

| Evidence | Where |
|---|---|
| Mutation adequacy of the ST20 scenario suite | 92.5% (`evals/results/mutation_st20.md`) |
| Scoring against a sealed answer key | `evals/answer_key/` — no model or tool reads it |
| Judge calibration for documentation scoring | `evals/results/judge_calibration.json` |
| Showcase runbook | `demo/RUNBOOK.md` |
| Design decisions, argued by five personas | `docs/debates/milestone-debates.md` |

## Layout

```
src/ladder_harness/  melsec · sim · plant · scenarios · lint · guard · render · router · ai · evaluation · mcp_server · cli
plant_data/          the EV-pack EOL cell (synthetic; see PROVENANCE.md)
config/              routing.yaml (lanes), pricing.yaml (sourced list prices)
evals/               task bank, sealed answer key, cassettes, results, REPORT.md
demo/                story and ledger pages, runbook, headless AGY script, playground
```

## Notice

MELSEC, iQ-F and GX Works3 are trademarks of Mitsubishi Electric Corporation. This project is not affiliated with or
endorsed by Mitsubishi Electric. Manuals are cited by number and never redistributed. All plant data is synthetic
and all physical values are representative. Licensed under Apache-2.0.
