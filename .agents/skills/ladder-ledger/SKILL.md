---
name: ladder-ledger
description: Show what the AI work cost and why each task ran on the model it did (horses for courses). Use when asked about cost, models, licences or routing.
---

# Horses for courses

1. `cost_ledger`, grouped by `profile,task_class`. Show dollars, calls and tokens.
2. Open `evals/REPORT.md` for the measured comparison: all-Opus, all-Opus-low, all-Flash and routed, over
   repeated runs. Quote the ranges exactly as printed. Never invent or round up a saving. If the report says
   routing did not beat Opus-low, say so.
3. Explain the lanes from `config/routing.yaml`:
   - deterministic work is $0;
   - bulk documentation runs on Flash;
   - the review gate runs on Opus;
   - repair runs on the lane the evaluations chose.
4. Remind the audience that the IDE agent's own tokens are billed to the AGY seat and are not in this ledger.
