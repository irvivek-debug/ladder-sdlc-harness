# Mutation adequacy — ST20

The reference program was mutated one defect at a time (flip a contact, drop a contact, halve or double a
preset, swap SET/RST, shift a comparison, drop an edge, swap a timer). A mutant is **killed** when any of the
22 ST20 scenarios fails.

**Score: 136/147 = 92.5%** (gate ≥ 90%). No mutants were invalid.

## Survivors

Every survivor is equivalent: none changes behaviour that the plant can produce. None is a missing test.

| Survivor | Mutation | Analysis |
|---|---|---|
| M001 | `LD< D100 K-500` → `LD<=` | Boundary only at exactly −5.00 kPa; a wire break reads −25 kPa. Equivalent. |
| M002 | `LD> D100 D123` → `LD>=` | Boundary only at exactly 20.00 kPa. Equivalent in practice. |
| M036 | S2 `ANI X21` removed | The clamp-open and clamp-closed switches cannot both be made on this plant, so the check is redundant. Equivalent (it would need a switch-discrepancy fault). |
| M047 | `AND>= D100 D122` → `AND>` | Fill completes one count (10 ms) later. Equivalent. |
| M053 | baseline `LD T22` → `LDI T22` | The rising edge of *not T22* fires one scan after stabilisation ends, so the baseline is taken 10 ms later. Equivalent. |
| M071 | `AND<= D112 D120` → `AND<` | Differs only for a decay of exactly 0.30 kPa. Boundary. |
| M074 | `AND> D112 D120` → `AND>=` | Same boundary as M071. |
| M086 | abort `ANI M205` removed | Re-triggering the abort while already in VENT changes nothing. Equivalent. |
| M105 | `AND< D100 K100` → `AND<=` | Boundary only at exactly 1.00 kPa. Equivalent. |
| M114 | S10 `ANI X20` removed | Clamp-open implies not clamp-closed on this plant (see M036). Equivalent. |
| M135 | fill valve `ANI M299` removed | Defence in depth. The abort rung resets FILL before the output rung runs, so a fault can never coexist with FILL at the fill-valve rung. Equivalent. |

## What the gate found (history)

The first run scored **78.9%**. Its survivors exposed two problems:

1. **Weak tests.** A pallet-sensor bounce restarted the sequence inside a single scan, and `never M201` could
   not see it. Fixes:
   - sequence-integrity invariants on every scenario;
   - step-duration checks taken from the parameter sheet;
   - four narrative-derived scenarios (FAT-ST20-10 … 13).
2. **A structural flaw in the reference program.** Output rungs sat above the step transitions, so the fill
   valve stayed open for one scan into STABILISE. The reference now drives all outputs after all transitions.

Regenerate this report with `python scripts/mutation_score.py ST20 --report evals/results/mutation_st20.md`,
then re-check the analysis column.
