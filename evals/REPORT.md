# Evaluation report — horses for courses on the EV-pack EOL cell

Sweep `S1` · generated 2026-09-26 · 415 scored samples (0 errored samples reported, not scored). Prices from `config/pricing.yaml` (Google Cloud list, read 2026-09-26). Gemini 3.1 Pro is a **preview** model.

## The four ways to staff the work

Workload: onboard and fix ST20 — document (T1), extract (T2), review (T4), and four repairs (D1, D3, D4, D5), each proven on the simulator. Median, with min–max over epochs.

| Profile | Configs (T1 / T2 / T3 / T4) | Cost per verified change — Flash intro price | — Flash 2027 price | Verified changes (of 4) | Defects caught before the plant (of 5) | Wall time |
|---|---|---|---|---|---|---|
| **all-pro** | pro-high / pro-high / pro-high / pro-high | $0.202 ($0.199–$0.216) | $0.202 ($0.199–$0.216) | 4 | 5 | 10.8 min (7.9 min–13.1 min) |
| **all-flash-high** | flash-high / flash-high / flash-high / flash-high | $0.198 ($0.195–$0.232) | $0.397 ($0.390–$0.463) | 4 | 5 | 30.9 min (24.2 min–36.5 min) |
| **all-flash** | flash-medium / flash-medium / flash-medium / flash-medium | $0.083 ($0.071–$0.092) | $0.166 ($0.143–$0.184) | 4 | 5 | 12.3 min (9.3 min–19.2 min) |
| **routed** | flash-low / flash-low / flash-medium / flash-medium | $0.076 ($0.064–$0.086) | $0.152 ($0.129–$0.173) | 4 | 5 | 10.3 min (9.6 min–20.2 min) |

**Honesty clause (milestone M4):** routed costs 62% less than the premium model everywhere and 9% less than the simplest alternative (Flash medium for everything) per verified change. 

Claude Opus 5.5 was not enabled in the project during this sweep, so every lane is Gemini; the harness supports Opus on Vertex and the sweep can add it with `--configs opus-low,opus-medium`.

## Lanes chosen from the evidence

- **T1 bulk documentation → `flash-low`** (cheapest config not significantly below the best (one-sided Fisher, alpha=0.05)).
- **T2 extraction → `flash-low`** (cheapest config not significantly below the best (one-sided Fisher, alpha=0.05)).
- **T3 repair until the gate passes → `flash-medium`** (cheapest config not significantly below the best (one-sided Fisher, alpha=0.05)).
- **T4 semantic review → `flash-medium`** (best mean recall (review gate; cost aside)).

## T1 bulk documentation

| Config | Model / effort | n | Pass rate | Mean cost | mean_quality | mean_coverage | Errors |
|---|---|---|---|---|---|---|---|
| flash-low | gemini-3.8-flash / low | 15 | 100% | $0.0067 | 0.974 | 1.0 | 0 |
| flash-medium | gemini-3.8-flash / medium | 15 | 100% | $0.0157 | 0.968 | 1.0 | 0 |
| flash-high | gemini-3.8-flash / high | 15 | 100% | $0.0376 | 0.969 | 1.0 | 0 |
| pro-high | gemini-3.1-pro-preview / high | 15 | 100% | $0.0597 | 0.974 | 1.0 | 0 |

## T2 extraction

| Config | Model / effort | n | Pass rate | Mean cost | Errors |
|---|---|---|---|---|---|
| flash-low | gemini-3.8-flash / low | 15 | 100% | $0.0081 | 0 |
| flash-medium | gemini-3.8-flash / medium | 15 | 100% | $0.0211 | 0 |
| flash-high | gemini-3.8-flash / high | 15 | 100% | $0.0499 | 0 |
| pro-high | gemini-3.1-pro-preview / high | 15 | 100% | $0.0645 | 0 |

## T3 repair until the gate passes

| Config | Model / effort | n | Pass rate | Mean cost | pass@1 | pass@3 | cost_per_verified_change | Errors |
|---|---|---|---|---|---|---|---|---|
| flash-medium | gemini-3.8-flash / medium | 50 | 100% | $0.0711 | 1.0 | 1.0 | $0.0711 | 0 |
| pro-high | gemini-3.1-pro-preview / high | 50 | 100% | $0.1104 | 1.0 | 1.0 | $0.1104 | 0 |
| flash-high | gemini-3.8-flash / high | 50 | 100% | $0.1520 | 1.0 | 1.0 | $0.1520 | 0 |

## T4 semantic review

| Config | Model / effort | n | Pass rate | Mean cost | mean_recall | false_positives_per_review | injection_flag_rate | Errors |
|---|---|---|---|---|---|---|---|---|
| flash-medium | gemini-3.8-flash / medium | 40 | 95% | $0.1121 | 1.0 | 0.05 | 0.875 | 0 |
| flash-high | gemini-3.8-flash / high | 40 | 95% | $0.1853 | 1.0 | 0.05 | 0.85 | 0 |
| pro-high | gemini-3.1-pro-preview / high | 40 | 92% | $0.2191 | 1.0 | 0.07 | 0.875 | 0 |

## Red team

| Config | Model / effort | n | Pass rate | Mean cost | tool_bypasses | model_compliance_rate | Errors |
|---|---|---|---|---|---|---|---|
| flash-medium | gemini-3.8-flash / medium | 25 | 100% | $0.0198 | 0 | 0 | 0 |

## Judge calibration (T1 accuracy)

- `gemini-3.1-pro-preview:high`: 100% agreement on 42 author-labelled pairs — **kept**
- `gemini-3.8-flash:high`: 100% agreement on 42 author-labelled pairs — **kept**

## Are the tests strong enough to judge AI output?

ST20 scenario suite mutation Score: 136/147 = 92.5%** (gate ≥ 90%). No mutants were invalid. — see `evals/results/mutation_st20.md`.

## Method and limits

- Every sample is scored against the sealed answer key (`evals/answer_key/`), which no model packet includes.
- Repairs pass only through the apply gate: parse → SAFETY guard → no new lint errors → targets fixed and no scenario regressions.
- The red team counts model compliance and tool-layer bypasses separately; the tool layer is deterministic.
- Costs are token costs of the harness's model calls. The IDE agent's own tokens (for example AGY's front-desk model) are billed to the seat and are not included.
- The data set is one synthetic cell. These results show the method; they are not a benchmark of the models in general.
