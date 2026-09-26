# Sealed answer key

**Evals and tests only.** Nothing in this directory is shown to a routed model, exposed through an MCP
tool, or meant to be read by an IDE agent working on the plant programs. `AGENTS.md` says so; the eval
harness enforces it by building every model packet from `plant_data/` alone.

| File | What it holds |
|---|---|
| `st20_golden.il`, `st10_golden.il` | the intended programs; `plant_data/.../legacy.il` = golden + seeded defects, documentation stripped |
| `defects.yaml` | every seeded defect as a patch on the golden program, its consequence, and the scenarios meant to catch it |
| `realism.yaml` | the deliberate mess (narrative drift, spare input, tag case, comment gaps) and the red-team plant |
| `golden_comments.csv` | complete device comments — the reference for documentation (T1) scoring |
