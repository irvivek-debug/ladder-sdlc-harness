# Evaluation report — horses for courses on the EV-pack EOL cell

Sweep `S1` · generated 2026-09-26 · 325 scored samples (0 errored samples reported, not scored). Prices from `config/pricing.yaml` (Google Cloud list, read 2026-09-26). Gemini 3.1 Pro is a **preview** model.

## Lanes chosen from the evidence

- **T2 extraction → `flash-low`** (cheapest config not significantly below the best (one-sided Fisher, alpha=0.05)).
- **T3 repair until the gate passes → `flash-medium`** (cheapest config not significantly below the best (one-sided Fisher, alpha=0.05)).
- **T4 semantic review → `flash-medium`** (best mean recall (review gate; cost aside)).

## T2 extraction

| Config | Model / effort | n | Pass rate | Mean cost | Errors |
|---|---|---|---|---|---|
| flash-low | gemini-3.8-flash / low | 15 | 100% | $0.0081 | 0 |
| flash-medium | gemini-3.8-flash / medium | 15 | 100% | $0.0211 | 0 |

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

- `gemini-3.8-flash:high`: 100% agreement on 42 author-labelled pairs — **kept**

## Are the tests strong enough to judge AI output?

ST20 scenario suite mutation Score: 136/147 = 92.5%** (gate ≥ 90%). No mutants were invalid. — see `evals/results/mutation_st20.md`.

## Method and limits

- Every sample is scored against the sealed answer key (`evals/answer_key/`), which no model packet includes.
- Repairs pass only through the apply gate: parse → SAFETY guard → no new lint errors → targets fixed and no scenario regressions.
- The red team counts model compliance and tool-layer bypasses separately; the tool layer is deterministic.
- Costs are token costs of the harness's model calls. The IDE agent's own tokens (for example AGY's front-desk model) are billed to the seat and are not included.
- The data set is one synthetic cell. These results show the method; they are not a benchmark of the models in general.
