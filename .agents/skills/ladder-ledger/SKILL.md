---
name: ladder-ledger
description: Show what the AI work cost and why each task ran on the model it did (horses for courses). Use when asked about cost, models, licences or routing.
---

# Horses for courses

1. `cost_ledger`, grouped by `profile,task_class`. Show dollars, calls and tokens.
2. Open `evals/REPORT.md` for the measured comparison: Pro everywhere, Flash high everywhere, Flash medium everywhere and routed, over
   repeated runs. Quote the ranges exactly as printed. Never invent or round up a saving. Say plainly that
   maximum effort bought nothing on this workload.
3. Explain the lanes from `config/routing.yaml`:
   - deterministic work is $0;
   - documentation and narrative extraction run on Flash at low effort;
   - review and repair run on Flash at medium effort, because the evidence showed the premium model and maximum effort
     added nothing here.
4. Remind the audience that the IDE agent's own tokens are billed to the AGY seat and are not in this ledger.
