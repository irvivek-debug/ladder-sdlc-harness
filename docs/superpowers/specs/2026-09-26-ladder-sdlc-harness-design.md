# Ladder SDLC Harness — Design Spec

**Date:** 2026-09-26 · **Status:** approved milestone-by-milestone (M0–M7) in the design session · **Repo:** `irvivek-debug/ladder-sdlc-harness` (private first)

> "AI proposes, the simulator proves, the engineer signs."

A harness that lets instrumentation and controls engineers take a MELSEC (Mitsubishi FX5-dialect)
ladder program through its whole software lifecycle — understand, document, change, test, review —
from any MCP-capable IDE, with each task routed to the cheapest model that is proven good enough
for it. The showcase runs on Google Antigravity (AGY); the closing message is **horses for courses:
different intelligence for different tasks, to optimise cost per verified change**.

The persona debates behind every ruling are in `docs/debates/milestone-debates.md`. The personas
are role-play devices for design, not statements by any company.

---

## 1. Positioning and metrics (M0)

- **Job to be done:** change a running line's program safely — understand someone else's undocumented
  ladder, change it, prove the change before it reaches the plant. Not "AI writes ladder".
- **Audience:** Mitsubishi product/engineering leaders first (15-minute scripted showcase), then their
  controls engineers (clone the repo, play in any IDE).
- **Governing metrics (MECE):**
  | Pillar | Metric | Source |
  |---|---|---|
  | Speed | engineer-hours per change (harness wall-clock as the proxy) | measured by the harness |
  | Quality | seeded defects caught before the plant (of 5) | sealed answer key |
  | Knowledge | share of devices and rungs documented | deterministic count |
  | Cost | cost per verified change, as a range | cost ledger over ≥5 eval runs |
- The licence story appears only in the close, framed as cost per verified change.
- External benchmarks (e.g. McKinsey developer-productivity research) appear only if verified
  against the primary source, printed with title/publisher/year, and paired with the harness's own
  measured figure. Unverifiable → not printed.

**Non-goals:** writing to or downloading to a real PLC (no PLC communication code exists in the repo);
authoring safety-instrumented functions; replacing GX Works3; HMI, robots, motion, networks, PID tuning.

## 2. Scenario (M1)

An **EV battery-pack end-of-line cell** on one FX5U-class PLC. Station records reuse the automotive
estate's ID formats (`plant_id`, `line_id`, `battery_batch_id`) so a warranty link can be drawn on a
slide later; the harness has **no** dependency on that estate or on BigQuery.

| Station | Role | Demo purpose |
|---|---|---|
| **ST10** pallet conveyor | photo-eyes, stopper, motor, jam detection | cheap bulk work (Flash documents many plain rungs) |
| **ST20** pressure-decay leak test | clamp → fill → stabilise → isolate/measure ΔP → compare → vent → unclamp; PT-2001 via analog adapter with scaling into a D register | the hero; instrumentation-heavy |
| **ST30** HV insulation (HiPot) test | black-box tester, start/pass/fail | **SAFETY**-classified; AI edits refused — the guardrail moment |

**Representative ST20 parameters** (labelled representative, reasoning shown in the narrative, never
presented as any OEM's specification): test pressure ≈ 15 kPa(g), stabilise 5 s, test 10 s,
ΔP limit 0.30 kPa over the test window, PT-2001 scaled 0–10000 = 0–100.00 kPa.

**Legacy program** ("migrated from an FX3 in 2019") with five seeded defects, each a patch on the sealed golden program. The golden program drives all outputs after all step transitions and implements the vented-before-unclamp permissive (C&E CE-ST20-08). The expected catcher is a
hypothesis; evals decide the real routing.

| # | Defect | Consequence | Expected catcher |
|---|---|---|---|
| D1 | Vent valve driven from two rungs (double coil): a 2021 manual-vent rung sits above the auto rung | latent: the manual vent button has done nothing since 2021 | T0 linter |
| D2 | ~60% of devices uncommented | unmaintainable | T1 Flash (bulk docs) |
| D3 | `OUT T200 K50` vent timer: 0.5 s on FX3 (10 ms range), 5.0 s on FX5 | +4.5 s cycle time per pack | T0 linter flags, simulator proves |
| D4 | Fill valve rung lacks clamp-closed interlock | pressurises an unclamped pack | C&E-derived test; T3/T4 |
| D5 | Baseline pressure `MOVP` triggered by the test-done timer instead of stabilise-done → ΔP ≈ 0 | **a leaking pack passes** | T4 semantic review (Opus); proven by "leaking pack must fail" |

Plus one red-team plant: a device comment instructing an AI assistant to remove an interlock.
Deliberate realism mess: narrative drift (narrative still says stabilise 3 s; the parameter sheet in the
I/O-list workbook — the authority scenarios are built from — and the code say 5 s; T4 should flag it), comment gaps,
one wired-but-unused spare input, inconsistent tag case. Every seeded item is recorded in the sealed
answer key.

## 3. Representation (M2)

- **Source of truth:** UTF-8 `.il` text, one MELSEC instruction per line, `;` comments, optional
  `#` line statements (GX Works3 parity). Rung boundaries are inferred (a load instruction after an
  output with empty logic/block stacks).
- **Interchange:** reader/writer for GX Works3 **ladder CSV of listed instructions** (UTF-16LE + BOM,
  tab-delimited, quoted, CRLF, must end with `END`; columns 8+ ignored on import) and **device-comment
  CSV**, per GX Works3 Operating Manual SH(NA)-081215ENG §6.3 and §6.8. The exact column layout is
  confirmed against the manual before the writer is coded. Files are labelled "generated by the harness
  in GX Works3 CSV format"; import into GX Works3 is **unverified** until someone runs it.
- **Instruction subset (v1):** LD LDI AND ANI OR ORI · LDP LDF ANDP ANDF ORP ORF · ANB ORB MPS MRD MPP
  INV · OUT (Y/M/L) · OUT/OUTH/OUTHS T (K or D preset) · OUT C · SET RST (incl. RST T/C/D) · PLS PLF ·
  MC MCR · END · 16-bit signed compares LD/AND/OR with = <> > < >= <= · MOV(P) · +(P) −(P) (2- and
  3-operand). Anything else raises `UnsupportedInstruction` — never skipped.
- **Devices:** X/Y octal (FX5), M, L, T0–511, C, D (16-bit signed), SM400/401/402, K decimal and
  H hex constants. Timer base is chosen by the instruction (OUT 100 ms, OUTH 10 ms, OUTHS 1 ms).
- **Reference card:** `reference/melsec_instruction_card.md` — our own paraphrase with manual page
  citations, used as retrieval context. Mitsubishi manuals are linked, never copied.

## 4. Architecture (M2)

Python ≥ 3.10 package `ladder_harness`. The deterministic core has no network and no model
dependency. Units, each with one purpose:

| Unit | Responsibility | Depends on |
|---|---|---|
| `melsec/` | device model, instruction table, `.il` parser/printer, rung segmentation, GX Works3 CSV + comment CSV I/O | — |
| `sim/` | FX5 scan engine on a virtual clock (fixed scan time, default 10 ms): input refresh → execute → output refresh; per-instance edge memory; timers update only when their coil executes; MC/MCR semantics (OUT off, non-retentive timers reset, SET/RST and counters hold) | `melsec` |
| `plant/` | station twins (ST10 kinematics, ST20 pressure physics with leak rate and thermal drift, ST30 black box) and fault injection (leak, stuck clamp sensor, over-pressure, PT wire break) | — |
| `scenarios/` | YAML scenario model (FAT-style names, stimuli over time, expectations), runner (sim + plant), generator from the C&E matrix | `sim`, `plant` |
| `lint/` | rules: double coil, unused/undeclared devices, FX3-range timer migration trap, timer read-before-coil (+2 scan), missing `END`, SAFETY-device writes | `melsec` |
| `render/` | series/parallel tree per rung → SVG ladder; rung diff with highlights; HTML report | `melsec` |
| `guard/` | SAFETY lock from the I/O list: refuses any patch touching SAFETY devices or rungs; apply-gate = parse + lint-clean + all scenarios pass | `melsec`, `scenarios` |
| `router/` | task classes, `config/routing.yaml`, backends (Vertex Gemini via `google-genai`, Vertex Claude via `anthropic[vertex]` `AnthropicVertex(region="global")`, replay cassettes), cost ledger (JSONL), `config/pricing.yaml` (every row: source URL + date read) | — |
| `ai/` | the model-backed tasks — explain/document (T1), extract (T2), generate/repair loop with simulator feedback (T3), semantic review (T4) — prompts + JSON schemas; structured output on every call | `router`, core |
| `mcp_server.py` | stdio MCP server: `ladder_parse`, `ladder_lint`, `ladder_simulate`, `ladder_render`, `ladder_diff`, `ladder_task`, `ladder_apply`, `ladder_export_gxw3`, `cost_ledger` | all |
| `cli.py` | `ladder` command mirroring the MCP tools | all |

**IDE surfaces:** `AGENTS.md` (rules for any agent), `.agents/` for Antigravity (skills
`ladder-explain`, `ladder-review`, `ladder-fix`, `ladder-ledger`, `ladder-playground`; rules;
`mcp_config.json`), and documented MCP setup for VS Code, Cursor, JetBrains, Claude Code. Antigravity
workflows are deprecated (retire 2026-11-01) — skills only.

**Model access:** Opus 5.5 is not in Antigravity's picker (it tops out at Opus 4.6), so all routed model
calls go through the harness to Vertex (Gemini Enterprise Agent Platform) using the caller's ADC login.
Model IDs: `gemini-3.8-flash` (thinking LOW/MEDIUM/HIGH), `gemini-3.1-pro-preview` (preview, global
only), `claude-opus-5-5` (effort low/medium/high; thinking always on; no forced tool choice — use
structured outputs). Opus refusal handling uses the SDK's client-side fallback middleware on Vertex.
The project ID comes from an environment variable, never from committed files.

**Replay mode:** every live call can be recorded to a cassette keyed by (task, model, effort, prompt
hash); replay serves them with zero credentials. Replayed output is labelled `REPLAY` wherever it is
shown. Cassettes carry no auth headers, project IDs or emails.

## 5. Data (M3)

`plant_data/ev_pack_eol/`: control narrative (`.md`), I/O list and C&E matrix (`.xlsx` + `.csv`),
per-station legacy `.il`, GX Works3-format CSV exports (UTF-16LE), device-comment CSVs, scenario YAML,
`PROVENANCE.md` (every file: synthetic/derived/real, source, licence). All synthetic content is ours,
Apache-2.0; ISA-5.1-style tags are written from scratch (PT-2001, ZS-2002, XV-2003 …).
`scripts/build_data.py` regenerates derived files deterministically.

**Sealed answer key** — `evals/answer_key/`: golden (fixed) programs, seeded-defect list, expected
findings, realism-mess list. Only evals and tests read it; MCP tools never expose it; routed models only
see packets the harness builds; `AGENTS.md` forbids agents from reading it.

**Cite, never copy:** Mitsubishi manuals (FX5 Programming Manual JY997D55801, FX5 User's Manual
Application JY997D55401, GX Works3 Operating Manual SH-081215ENG, FX3 Programming Manual JY997D16601),
ISA-5.1, IEC 61131-3, IEC 61508/61511, pressure-decay leak-test standard (verified before citing),
LLM4PLC / Agents4PLC / SemaPLC / the 2026 MELSEC FX IL benchmark. **Excluded:** GPL ladder datasets
(would force GPL), Agents4PLC tasks (ST, not MELSEC).

## 6. Routing and economics (M4)

| Class | Examples | Starting lane |
|---|---|---|
| T0 Deterministic | parse, lint, simulate, render, diff, scenarios from C&E | no model |
| T1 Bulk comprehension | device comments, rung explanations, change-record drafts | Gemini 3.8 Flash low |
| T2 Extraction | narrative → spec JSON, I/O list normalisation | Flash medium, schema-bound |
| T3 Generate/repair | write/fix rungs until scenarios pass (simulator feedback loop) | contest: Flash high / 3.1 Pro / Opus |
| T4 Semantic review | narrative vs code, failed-test root cause, interlock review | Opus 5.5 |
| T5 Guardrail | may a SAFETY rung change? | never a model |

- **Lane rule:** per class, the cheapest (model, effort) whose pass rate is statistically
  indistinguishable from the best (two-proportion test, α = 0.05). Exception: T4 interlock review
  takes the best reviewer by recall, cost aside. `routing.yaml` is generated from eval results.
- **Gemini 3.1 Pro** competes for T3 and is labelled "preview" wherever it appears.
- **Baselines** (all tasks): all-Opus (medium), all-Opus-low, all-Flash (medium), routed. ≥5 runs;
  report ranges (min–max and median); price at both Flash rates (intro to 2026-12-31 and from
  2027-01-01). Model-scoped caching losses are counted.
- **Honesty clause:** if routed does not beat Opus-low on cost per verified change, the close states what
  routing does buy (latency, volume headroom) instead of a manufactured saving.
- The IDE's own agent (Flash inside AGY) is the front desk; its tokens are billed to the AGY seat and
  labelled outside the ledger.

**Prices in `pricing.yaml` at design time (USD / 1M tokens, Vertex global, read 2026-09-26):**
Gemini 3.8 Flash 0.75 in / 3.75 out / 0.075 cached (intro to 2026-12-31), then 1.50 / 7.50 / 0.15;
Gemini 3.1 Pro preview 2.00 / 12.00 / 0.20 (≤200K); Claude Opus 5.5 4.00 / 20.00 / 0.20 cache read.
Each row carries its source URL; re-read before the showcase.

**Live-eval budget:** a hard cap of **USD 150 per full sweep**, enforced by the runner from the ledger
(abort, not warn). Smoke runs precede the sweep.

## 7. Evaluation (M5)

System of record: **pytest** (deterministic) + **Inspect AI** (model evals; native Vertex Gemini and
Claude providers). Vertex Gen AI Evaluation Service is an optional adapter for the explanation-quality
rubric only. promptfoo and DeepEval are not used.

| Concept | Gate |
|---|---|
| Parser round-trip (`print(parse(x)) == x`), metamorphic simulator tests (De Morgan rewrites, independent-rung reordering), GX Works3 CSV round-trip | all pass |
| Simulator semantics vs documented behaviour (timer bases, update-on-coil, +2-scan read-before-coil, octal X/Y, MC/MCR, edges) | all pass |
| Mutation testing of the scenario suite against the golden program (flip NO/NC, drop contact, change preset, swap SET/RST, retarget MOVP) | ≥ 90% of mutants killed |
| Execution-based scoring on T3 (pass@1, pass@3) | reported per model × effort |
| Seeded-defect recall and precision on T4 (variants with 0–3 defects, incl. clean controls) | scored vs answer key |
| LLM-as-judge for T1 explanations — cross-family judge, calibrated on hand labels | ≥ 80% agreement or judge dropped |
| Deterministic hallucination check on T1/T4 (every device named must exist) | reported |
| Red team: injected comments, SAFETY edits, "download to PLC" requests | **0 bypasses**, tested at model and tool layers |
| Cost per successful task | feeds `routing.yaml` |
| CI (GitHub Actions) | deterministic tests + replay-mode evals on every push; no credentials, $0 |

**Task bank (~42):** T1 ×8, T2 ×6, T3 ×14 (add fill-timeout alarm, add over-pressure trip, fix each of
D1/D3/D4/D5, port FX3 rungs, ST10 jam detection from narrative, …), T4 ×8, red team ×6. Plant twin fault
injection covers the unhappy paths. Leaders see one ledger; detail lives in `evals/REPORT.md`.

## 8. Demo (M6)

~15 minutes, value first, technology disclosed progressively. `demo/RUNBOOK.md` gives every beat exact
prompts, timing, expected output, a recorded fallback and a reset command.

| Beat | Min | Content | Horse |
|---|---|---|---|
| 1 The escape | 2 | one-page story (`demo/story.html`): a leaking pack passed; the four metrics; no tech nouns | — |
| 2 Understand | 2 | `/ladder-explain ST20`: linter already found D1 + D3 for $0; Flash documents every device for cents | T0 + T1 |
| 3 Find | 3 | `/ladder-review ST20`: Opus finds D5; "leaking pack must fail" goes red on legacy | T4 |
| 4 Fix and prove | 3 | `/ladder-fix`: first recorded proposal looks right and the simulator rejects it; second passes; rung diff drawn as ladder; mutation score | T3 |
| 5 Guardrail | 1 | ask to change ST30 or trigger the injected comment → deterministic refusal | T5 |
| 6 Horses for courses | 2 | four-column ledger (from the ≥5-run eval sweep, labelled so) + close | — |
| 7 Your turn | 2 | same MCP server in a second client; replay quickstart; playground challenges | — |

- `demo/preflight.py` (run 10 minutes before) checks ADC, model reachability for all three models,
  quota, and pricing freshness, then sets live or replay mode.
- `demo/run_headless.sh` plays the arc through `agy -p … --output-format json` (recording and backup);
  each step asserts `status == "SUCCESS"`.
- **Verification boundary:** built and verified end-to-end against `agy` in the Argolis Cloud Shell
  (reached from the Mac via `gcloud cloud-shell ssh/scp`); MCP portability verified in Claude Code; the
  Antigravity IDE workspace (`.agents/`) is shipped but verified by the presenter only. Cloud Shell gets the
  code by `gcloud cloud-shell scp` (its `gh` is not logged in; no workaround is attempted).
- `demo/playground/CHALLENGES.md`: five engineer challenges; fixes export to GX Works3 CSV.
- "Jetski" stays off anything public.

## 9. Landing (M7)

- Repo `irvivek-debug/ladder-sdlc-harness`, **private first**, Apache-2.0, `NOTICE` with trademark
  disclaimer ("MELSEC and GX Works3 are trademarks of Mitsubishi Electric; this project is not affiliated
  with or endorsed by Mitsubishi Electric"). Debates marked as role-play.
- Before any flip to public: `scripts/scrub_check.py` must pass — no project IDs, account emails, or
  customer-pursuit wording anywhere in the tree or history.
- `scripts/secret_scan.sh` before every commit; files staged by name, never `git add -A`.
- Commits are local; **every push needs the owner's explicit go-ahead.**
- README opens with a 60-second replay-mode quickstart needing zero credentials.

## 10. Risks, dependencies, unverified items

| Item | Handling |
|---|---|
| Opus 5.5 / Gemini 3.8 Flash / 3.1 Pro enabled in the GCP project | preflight checks; if Opus is not enabled, the owner enables it in Model Garden (not worked around) |
| ADC login expiry | owner re-runs `gcloud auth application-default login`; work waits |
| GX Works3 CSV import | unverified until run in GX Works3; labelled so |
| Gemini 3.1 Pro is preview | labelled; lane only if earned |
| Prices change (Flash intro ends 2026-12-31) | both rates shown; preflight flags pricing older than 14 days |
| agy CLI MCP config (workspace `.agents/mcp_config.json` vs global) | verified in Cloud Shell; global config written only with the owner's OK |
| Mac has Python 3.9 only | `uv` installed as a binary in `~/.local/bin` provides Python 3.12 |
| Router cannot beat Opus-low | honesty clause (§6) |

## 11. Success criteria

1. `pytest` green; mutation score ≥ 90%; red team 0 bypasses.
2. Live sweep complete within the USD 150 cap; `routing.yaml` generated from results; four-baseline ledger
   with ranges.
3. Replay-mode demo runs end-to-end with zero credentials in under 2 minutes.
4. Headless `agy` run of the arc succeeds in Cloud Shell (every step `SUCCESS`).
5. MCP server verified in `agy` and Claude Code.
6. Local commits clean of secrets and scrub findings; private push only on the owner's go-ahead.

---

## Execution addendum (2026-09-26)

- Claude Opus 5.5 was not enabled for the evaluation project, so, at the owner's direction, the sweep ran on Gemini
  only: Gemini 3.8 Flash (low, medium and high effort) and Gemini 3.1 Pro (preview, high) as the premium comparison.
  Opus support stays in the router.
- Documentation accuracy is judged by a different Gemini model (Flash judged by 3.1 Pro, and 3.1 Pro by Flash). Both
  judges passed calibration at 42/42; the report notes the departure from cross-family judging.
- Result (sweep S1, 415 samples, about $43):
  - Every lane is Flash. T1 and T2 run at low effort; T3 and T4 at medium.
  - Routing costs $0.076 per verified change: 62% less than Pro everywhere and 9% less than Flash-medium everywhere.
  - Every profile fixed 4 of 4 changes and caught 5 of 5 defects.
- Reviewers found four real flaws in the author's reference program. Each was confirmed on the simulator and recorded
  in `evals/answer_key/latent.yaml`.
