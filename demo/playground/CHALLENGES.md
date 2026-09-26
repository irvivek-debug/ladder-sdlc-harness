# Playground — five challenges

Each challenge ends when `ladder apply` passes: the SAFETY guard, no new lint errors, the target scenarios fixed and no
regressions. Start with the free tools; `ladder lint`, `ladder simulate` and `ladder diff` cost nothing.

| # | Challenge | Target scenarios | Hint |
|---|---|---|---|
| 1 | **The dead button.** In manual mode the ST20 manual vent pushbutton does nothing. Fix it without changing automatic venting. | `FAT-ST20-06` | Rule L001. The last write to a coil in a scan wins. |
| 2 | **Lost time.** ST20 misses its 23.0 s cycle allowance. Recover 4.5 s. | `FAT-ST20-04` | Rule L002, and the FX3→FX5 timer section of `reference/melsec_instruction_card.md`. |
| 3 | **Jam.** ST10 has no jam detection. Add it from narrative §3. | `CE-ST10-03` | The entry eye is X11; the parameter sheet gives the time. |
| 4 | **Clamp slip.** The fill valve must close the moment the clamp is lost during FILL. | `CE-ST20-01` | Compare the fill-valve rung with C&E row CE-ST20-01. |
| 5 | **Break the guard.** Try `ladder apply ST30 demo/playground/st30_no_guard.il`. | none | Watch the gate refuse at the `guard` stage. That refusal is deterministic, not a model's opinion. |

Useful commands:

```bash
ladder simulate ST20 --only FAT-ST20-06          # prove it fails now
ladder task repair ST20 --goal "..." --targets FAT-ST20-06
ladder diff ST20 demo/out/st20_candidate.il
ladder apply ST20 demo/out/st20_candidate.il --targets FAT-ST20-06
ladder export ST20                                # GX Works3 CSV (import unverified)
```
