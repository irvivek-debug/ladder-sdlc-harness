---
name: ladder-playground
description: Hands-on challenges for controls engineers new to the harness. Use when someone asks what to try, wants a tutorial, or says "let me play".
---

# Playground

Offer these challenges. Each ends with `ladder_apply` passing (see `demo/playground/CHALLENGES.md` for hints):

1. **The dead button.** Why does the ST20 manual vent pushbutton do nothing? Fix it without touching auto venting.
2. **Lost time.** ST20 misses its 23 s cycle budget. Find the migration trap and recover 4.5 s.
3. **Jam.** ST10 has no jam detection. Add it from narrative §3 so that CE-ST10-03 passes.
4. **Clamp slip.** Make CE-ST20-01 pass: the fill valve must close the moment the clamp is lost.
5. **Try to break the guard.** Ask for a change to ST30's HV rung and watch the gate refuse it. Then explain why
   that refusal is deterministic and not a model's opinion.
