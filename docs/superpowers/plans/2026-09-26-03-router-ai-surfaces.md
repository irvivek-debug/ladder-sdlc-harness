# Plan 3 — Router, AI Tasks, MCP Server, CLI and IDE Surfaces

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans. Same deviation note as Plan 2
> (interfaces, algorithms and tests fixed here; bodies written straight into source; TDD-first).

**Goal:** Route each lifecycle task to the right model on Vertex (or a recorded answer), price every call,
and expose the whole harness to any MCP-capable IDE, a CLI, and Antigravity skills.

**Spec:** §4 (router, ai, mcp_server, cli, IDE surfaces), §6 (routing + economics), §8 (replay).

## Global Constraints

- Model IDs: `gemini-3.8-flash` (thinking LOW/MEDIUM/HIGH), `gemini-3.1-pro-preview` (global only, preview),
  `claude-opus-5-5` (effort low/medium/high; thinking always on; structured output via
  `output_config.format`; no forced tool choice). Region/location `global`.
- SDKs: `google-genai` (`genai.Client(vertexai=True, project, location="global")`,
  `types.GenerateContentConfig(system_instruction, response_mime_type="application/json",
  response_json_schema, thinking_config=types.ThinkingConfig(thinking_level=...), max_output_tokens)`;
  usage from `usage_metadata.{prompt,candidates,thoughts,cached_content}_token_count`).
  `anthropic[vertex]` 1.x (`AnthropicVertex(project_id, region="global")`, `messages.create(...,
  output_config={"effort": e, "format": {"type": "json_schema", "schema": s}})`; check `stop_reason == "refusal"`
  before reading content; usage `input_tokens`, `output_tokens`, `cache_read_input_tokens`).
- Auth is the caller's ADC login. Project from env `LADDER_GCP_PROJECT` (fallback `GOOGLE_CLOUD_PROJECT`); never committed.
- Model packets are built from `plant_data/` only — never `evals/answer_key/`.
- Every model call writes one ledger line; replayed calls are labelled `backend: replay`.
- Plant text is data: prompts wrap it in tagged blocks and instruct the model that instructions inside data
  are not instructions (red-team plant on X20).

## Task 1: Pricing, routing config, ledger
Files: `config/pricing.yaml`, `config/routing.yaml`, `src/ladder_harness/router/{__init__,pricing,ledger}.py`; tests `tests/router/test_pricing_ledger.py`.
- `Pricing.load(path)`; `price(model, usage, on: date) -> float` (input excl. cached × input rate + cached × cached rate + (output + thinking) × output rate); `price_both(model, usage) -> {"intro": .., "list": ..}` for models with period pricing.
- `Ledger(path)`; `append(entry: dict)`; `read() -> list[dict]`; `summary(rows, group_by=("profile","task_class")) -> list[dict]`.
- Tests: Flash intro vs 2027 price for a fixed usage; Opus price; thinking tokens billed as output; ledger round-trip and grouping.

## Task 2: Backends and router
Files: `src/ladder_harness/router/{types,backends,replay,router}.py`; tests `tests/router/test_router.py`.
- `ModelCall(task_class, model, effort, system, prompt, schema, max_output_tokens=16000)`; `Usage(input, output, thinking, cached)`;
  `ModelResult(data, text, usage, latency_s, model, effort, backend, cost_usd, key)`.
- `VertexGemini`, `VertexClaude` (lazy SDK import; raise `BackendUnavailable` with the exact auth command on
  credential failure), `ReplayBackend(cassette_dir)`, `Recorder(inner, cassette_dir)`.
- Cassette key = sha256 of canonical JSON {task_class, model, effort, system, prompt, schema}; file
  `evals/cassettes/<key>.json` holds the result minus secrets.
- `Router(routing, pricing, ledger, mode, backends)`; `lane(task_class, profile) -> (model, effort)`;
  `call(task_class, system, prompt, schema, profile="routed", meta=None) -> ModelResult`.
  Modes: `live`, `record` (live + write cassette), `replay` (cassette or `ReplayMiss`), `auto` (replay if present, else live).
- Tests with a fake backend: lane selection per profile; record→replay round trip yields identical data and
  `backend="replay"`; replay miss raises; ledger line per call with cost.

## Task 3: Packets, prompts, schemas, tasks
Files: `reference/melsec_instruction_card.md`, `src/ladder_harness/ai/{__init__,packets,prompts,schemas,tasks}.py`; tests `tests/ai/test_tasks.py`.
- `build_packet(cell, station, parts)` → tagged text blocks (`<program>`, `<device_comments>`, `<io_list>`,
  `<parameters>`, `<cause_effect>`, `<narrative>`, `<lint>`), stable order for caching; asserts no path under
  `evals/answer_key` is ever read.
- Tasks (each returns a dataclass with `result`, `calls: list[ModelResult]`, post-check notes):
  `explain(router, cell, station)` T1 → device comments ≤ 32 chars + rung purposes; post-check drops devices not in program.
  `extract(router, cell, station)` T2 → parameters/sequence/interlocks/alarms + `conflicts` vs parameter sheet.
  `review(router, cell, station)` T4 → findings {title, category ∈ [double_coil, timing, missing_interlock,
  semantic_logic, documentation, suspicious_instruction, safety, other], severity, rungs, devices, evidence,
  consequence, proposed_fix, confidence}.
  `repair(router, cell, station, goal, max_attempts=3)` T3 → loop: ask for a full candidate program; run the
  apply gate (parse → guard → lint → scenarios); feed the gate's reasons back; stop on pass. Returns attempts
  with gate stages; `pass@k` is derived from these.
- Tests with scripted fake backends: repair loop passes on attempt 2 after a scenario failure is fed back; guard
  refusal is fed back verbatim; explain post-check strips hallucinated devices; packets never contain answer-key text.

## Task 4: MCP server and CLI
Files: `src/ladder_harness/{mcp_server,cli,workspace}.py`; tests `tests/test_surfaces.py`.
- `Workspace(root)` resolves the cell, config, ledger (`logs/ledger.jsonl`), cassettes, output dir `demo/out/`.
- MCP tools (plain functions registered on `MCPServer`, with `FastMCP` fallback for SDK 1.x):
  `ladder_parse`, `ladder_lint`, `ladder_simulate`, `ladder_render`, `ladder_diff`, `ladder_task`,
  `ladder_apply` (writes `plant_data/<cell>/<station>/proposed.il` only when the gate passes; never overwrites
  legacy), `ladder_export_gxw3`, `cost_ledger`. No tool talks to a PLC.
- CLI `ladder <cmd>` mirroring the tools, plus `ladder mutate STATION`.
- Tests call the tool functions directly (no transport) and run `python -m ladder_harness.cli lint ST20`.

## Task 5: IDE surfaces
Files: `AGENTS.md`, `.agents/rules/ladder-harness.md`, `.agents/skills/{ladder-explain,ladder-review,ladder-fix,ladder-ledger,ladder-playground}/SKILL.md`,
`.agents/mcp_config.json`, `.mcp.json` (Claude Code), `.vscode/mcp.json`, `docs/ide-setup.md`, `scripts/install_ide.py`.
- Verified: MCP in Claude Code (this machine) via a stdio handshake test; agy in Cloud Shell in Plan 5.

## Task 6: Live smoke (needs ADC)
`scripts/smoke_models.py` — one tiny schema-bound call per model in `record` mode; prints tokens, cost, latency.
Blocked until the owner renews ADC; everything else proceeds offline.
