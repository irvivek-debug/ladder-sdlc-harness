# Milestone debates

Every key milestone of this harness was argued out by five role-play personas before a ruling was
approved. The personas are design devices — they do not speak for any company.

| Persona | Stake |
|---|---|
| **Product manager** (PLC vendor) | the problem, the engineers' jobs to be done, the safety line |
| **Cloud architect** (model platform) | consumption: Gemini, AGY seats, Opus on Vertex — one bill |
| **AI engineer** | the router and the evaluation suite; nothing claimed that isn't measured |
| **Controls engineer** | subject-matter realism, the raw files, the person who uses the harness |
| **Demo director** | the 15-minute story and the closing message |

Research that fed the debates (verified 2026-09-26, sources in the spec and `plant_data/.../PROVENANCE.md`):
GX Works3 has no IL editor but imports/exports ladder as listed-instruction CSV; FX5 selects timer base
by instruction (OUT 100 ms / OUTH 10 ms / OUTHS 1 ms) while FX3 selects it by device range; no reusable
open MELSEC IL parser or simulator exists; Antigravity's model picker tops out at Opus 4.6 while
`claude-opus-5-5` is GA on Vertex; Opus 5.5 costs ~5.3× Gemini 3.8 Flash per token at Flash's
introductory price and ~2.7× after it ends; promptfoo is now OpenAI-owned.

---

## M0 · What are we selling, and to whom?

- **Product manager:** Engineers don't want AI to *write* ladder — they don't trust it. The job is
  *changing a running line's program safely*: understand someone else's undocumented code, change it,
  prove it before it reaches the plant. The vendor's stake: as the engineers who wrote those programs
  retire, customers stay with the PLC that is easiest to change safely.
- **Cloud architect:** Leaders buy consumption. Show Gemini carrying most of the work and Opus as the
  premium specialist, all on one cloud bill. Wants the per-engineer cost slide early.
- **AI engineer:** No productivity number goes on screen unless the harness measured it. The claims we can
  defend are "every AI change is proven on a simulator" and cost per *verified* change.
- **Controls engineer:** The real fear is a 2 a.m. breakdown in code nobody documented. Two red lines: AI
  never downloads to a PLC, and the harness sits *beside* GX Works3 (CSV round-trip), not in place of it.
- **Demo director:** Leaders remember one story. Open on "the leak test that passed a leaking pack";
  close on the cost ledger.

**Clash:** licence story first (architect) vs plant story first (PM, director). Settled by the standing
rule: value first, technology disclosed progressively.

**Ruling:** Position as "AI proposes, the simulator proves, the engineer signs." Four metrics — speed,
quality, knowledge, cost (cost per verified change, as a range). Licence maths only in the close. External
benchmarks only if verified at source and paired with the harness's own measured figure.

## M1 · Scope and scenario

- **Controls engineer:** One FX5U, three stations. ST20's sequence: clamp → fill → stabilise → isolate and
  measure the drop → compare → vent → unclamp. Transducer through an analog adapter into a D register; X/Y
  octal; ST30 tagged SAFETY. The legacy program was "migrated from an FX3 in 2019" — which honestly explains
  the timer trap.
- **AI engineer:** Three stations won't give pass@k any meaning. Needs a bank of ~40 tasks plus mutants of
  the golden program.
- **Cloud architect:** Link the station to the automotive data estate — VIN → battery batch → leak result →
  warranty claim — to show the data platform.
- **Product manager:** Scope creep. The harness must stand alone on a laptop. Out: HMI, robots, motion,
  networks, PID tuning, safety PLCs.
- **Demo director:** ST20 is the hero, ST10 the cheap bulk work, ST30 the guardrail moment.

**Clash:** the data-estate link vs stand-alone.

**Ruling:** Stand-alone; records reuse the estate's ID formats so the warranty link can be drawn on a slide
later. Five seeded defects (double coil; comment gaps; FX3→FX5 timer trap costing +4.5 s per pack; missing
clamp interlock; baseline captured on the wrong edge so a leaking pack passes) plus one injected-comment
red-team plant. Which "horse" catches each is a hypothesis the evals test.

## M2 · Representation and architecture

- **Controls engineer:** Engineers think in rungs — they must *see* ladder. The dialect must be real MELSEC,
  not an invented DSL.
- **AI engineer:** Models are measurably poor at graphical ladder; instruction-list mnemonics are compact
  text, and a reference card lifts accuracy. The parser is the gate: unparseable output is rejected with the
  error fed back.
- **Product manager:** Don't rebuild GX Works3. The harness is a test bench and reviewer; GX Works3 stays the
  editor. Label the CSV round-trip unverified until it is run in GX Works3.
- **Cloud architect:** MCP is the hero — one server, every IDE. Host it on Cloud Run.
- **AI engineer and product manager (against):** Local first — plant code should not leave the laptop, only
  the prompt.
- **Demo director:** Ladder rendered as a picture in the IDE, diff highlighted. Replay mode non-negotiable,
  and visibly labelled.

**Clashes:** graphics vs text (text is truth, pictures rendered one-way); Cloud Run vs local (local first).

**Ruling:** `.il` text is canonical, with GX Works3 CSV and comment-CSV converters; an FX5 scan simulator on
a virtual clock; per-station plant twins; `ladder` CLI + stdio MCP server + `AGENTS.md` + Antigravity
skills; a router with Vertex and replay backends and a cost ledger priced from a sourced `pricing.yaml`;
structural guardrails — SAFETY devices locked, and no PLC communication code in the repo at all.

## M3 · Sourcing the raw files

- **Controls engineer:** Real files are messy — stale narrative, half-empty comments, a wired-but-unused
  spare, inconsistent tag case. Clean data makes a toy.
- **Product manager:** No real customer files. Everything is synthetic or permissively licensed, with a
  provenance manifest.
- **AI engineer:** A sealed answer key the evals read and nothing else sees.
- **Cloud architect:** Stable IDs and CSVs so the data could load into a warehouse later.
- **Demo director:** Ship the C&E matrix as `.xlsx` — that's what engineers actually open.

**Ruling:** Synthetic files are ours (Apache-2.0) in the formats engineers receive; Mitsubishi manuals,
ISA/IEC standards and papers are cited, never copied; GPL datasets are excluded; the realism mess is
deliberate and recorded in the sealed key; physical values are labelled representative.

## M4 · Horses for courses: routing and economics

- **Cloud architect:** Gemini visibly carries the volume, 3.1 Pro gets a role, Opus is the premium
  specialist. Show both Flash prices — the introductory rate ends 2026-12-31.
- **AI engineer:** The routing table is an eval output, not a sales decision. 3.1 Pro (preview) earns a lane
  or doesn't get one. The fair baseline includes Opus at low effort for everything; if routing can't beat
  it, we say so. Caches are model-scoped, so a cascade loses some reuse — count it.
- **Product manager:** Engineers care about right and fast. Flash for interactive work, Opus for the review
  gate. Show a cost-per-engineer-month range with the usage profile stated.
- **Controls engineer:** Anything near interlocks goes to the strongest reviewer, whatever it costs.
- **Demo director:** The close is one picture: four columns (all-Opus, Opus-low, all-Flash, routed). If the
  numbers don't tell the story, we change the story, not the numbers.

**Clash:** a guaranteed 3.1 Pro lane vs evidence; "cost doesn't matter" vs the thesis.

**Ruling:** Cheapest (model, effort) statistically indistinguishable from the best, per class — except T4
interlock review, which takes the best reviewer by recall. That is still horses for courses: the premium
horse runs the one race where it matters. Four baselines, ≥5 runs, ranges, both Flash prices; an honesty
clause if routing does not beat Opus-low.

## M5 · Evaluation strategy

- **AI engineer:** pytest for the deterministic core; Inspect AI as the eval runner (neutral licence, native
  Vertex Gemini and Claude). Skip promptfoo for ownership optics; DeepEval isn't needed.
- **Cloud architect:** The Vertex Gen AI Evaluation Service should be visible.
- **Controls engineer:** Tests come from the C&E matrix and narrative an engineer signs — never from what
  the AI wrote. The plant twin injects faults: leak, stuck clamp sensor, over-pressure, transducer wire break.
- **Product manager:** Leaders get one number per column; detail sits behind a fold.
- **Demo director:** One live moment where the simulator rejects a fix that looked right.

**Ruling:** pytest + Inspect AI as system of record; Vertex Gen AI Eval as an optional adapter for the
explanation rubric. Gates: round-trip and metamorphic tests; mutation score ≥ 90% on the golden program;
pass@1/pass@3 on repair; seeded-defect recall and precision; judge calibration ≥ 80% with cross-family
judges; zero red-team bypasses; cost per successful task; replay-mode CI on every push.

## M6 · The demo script

- **Demo director:** Exact prompts, timings, recorded fallback and reset per beat; a preflight check decides
  live or replay; replay badged on screen.
- **Product manager:** Don't open in the IDE; no tech nouns in the first two beats.
- **Cloud architect:** The AGY moment and the one-bill line; prove portability in a second client — "best
  on AGY, works everywhere".
- **AI engineer:** Live calls use the eval code path; the ledger comes from the ≥5-run sweep, not n = 1, and
  says so.
- **Controls engineer:** A playground of five challenges for the engineers; fixes export to GX Works3 CSV.

**Ruling:** Seven beats in ~15 minutes — the escape, understand, find, fix and prove, guardrail, horses for
courses, your turn. Verified end-to-end against `agy` in Cloud Shell; Antigravity workspace shipped and
verified by the presenter; a headless `agy -p` script as recording and backup.

## M7 · Landing on GitHub

- **Product manager:** No vendor name on a cloud provider's repo; the dialect named only with a
  non-affiliation disclaimer; debates marked role-play.
- **Cloud architect:** Public makes it a reusable field asset.
- **Controls engineer:** Public means engineers can clone without asking.
- **AI engineer:** Public exposes cassettes and ledgers — scrub project IDs and emails; project ID from an
  environment variable; secret scan; stage by name.
- **Demo director:** README opens with a 60-second replay quickstart.

**Clash:** the debate log describes a sales motion toward a named company; public on day one would publish it.

**Ruling:** Private first, Apache-2.0, replay-mode CI; public only after a scrub check passes; local commits,
pushes only on explicit go-ahead.
