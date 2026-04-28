---
name: eval-flywheel-orchestrator
description: Portable eval loop orchestrator for trace-aware scoring, threshold gating,
  and regression detection with deterministic summaries.
metadata:
  version: 1.6.0
  short-description: Trace-aware eval loop and regression gate orchestration
  portability_tier: strict_zero_leak
  scope: global
  requires_env: []
  project_profiles: []
---

# Eval Flywheel Orchestrator

## Use When
- You need repeatable evaluation loops with explicit pass/fail policy.
- A baseline must be protected from regressions.
- You want artifacts suitable for CI and audits.

## Inputs
- `dataset.jsonl` (rows with score/baseline fields)
- optional `grader_spec.yaml`

## Outputs
- `eval_dataset.jsonl`
- `grader_spec.yaml`
- `eval_summary.json`

## Features
- Score threshold + regression gates.
- Gradient error checks (`gradient_abs_err`, `gradient_rel_err`).
- Stochastic confidence summaries from repeated samples.
- Metric-coverage reporting (`metric_coverage`) and missing-metric disclosure (`missing_metrics[]`).
- Objective weighting policy disclosure (`weight_policy_applied`) for reproducible gate math.
- Model-certification and pathology-gate support for generative outputs.
- Drift-aware recommendation checks:
  - interleaved baseline calibration summaries
  - recheck of top candidate against latest calibrated baseline
  - non-reproducible uplift fallback policy

## Additive Contract Notes (NEW v1.1)
`eval_summary.json` should include:
- `metric_coverage`
- `missing_metrics[]`
- `weight_policy_applied`
- `scoring_policy_version`

## Additive Contract Notes (NEW v1.2)
`eval_summary.json` should include:
- `drift_guard` (`enabled`, `calibration_count`, `decode_drift_pct`)
- `rechecked_speed_gain_pct`
- `enforced_baseline_fallback`

## Additive Contract Notes (NEW v1.3)
`eval_dataset.jsonl` and `eval_summary.json` should include frontier diagnostics:
- per-row `frontier_class` (`near_miss_frontier|success_frontier|below_frontier|quality_risk_frontier|unknown_frontier`)
- per-row optional `speed_gain_pct` and `quality_drop_pct`
- summary `frontier_diagnostics` with counts and dominant class

## Additive Contract Notes (NEW v1.4)
For generative-model certification, `eval_dataset.jsonl` and `eval_summary.json` should support:
- per-row `repetition_ratio`
- per-row `novelty_ratio`
- per-row `role_prefix_contamination`
- per-row `reasoning_leak_detected`
- per-row `pathology_gate_result` (`pass|warning|quarantine`)
- summary `quarantined_candidates[]`
- summary `certification_gate_result`

## Run
```bash
python3 scripts/run_eval.py --dataset dataset.jsonl --grader-spec grader_spec.yaml --out-dir out
```

## Validation
```bash
python3 scripts/run_eval.py --self-test
```

## References
- `references/contracts-v1.md`

## Hardware In The Loop And Environmental Canaries (NEW v1.4.1)
- When offline grading cannot prove real utility, require live environment canaries before promotion.
- This is mandatory for:
  - RF or RSSI sensing
  - camera/microphone pipelines
  - agent systems whose quality depends on real tools or external state
  - any system where room layout, signal path, or operator behavior matters
- The eval contract should capture:
  - `canary_stimulus`
  - `expected_state_change`
  - `observed_state_change`
  - `semantic_canary_result`

## Healthy But Useless Regression Gate
- Add a regression class for systems that are operationally alive but fail the user-visible objective.
- Promotion must be blocked if any of the following appear in the gated suite:
  - process/API healthy but obvious stimulus produces no meaningful state change
  - UI reports healthy while the product behavior remains inert
  - stale persisted metadata keeps the candidate trapped in a pre-fix regime
- Summaries should clearly separate:
  - `runtime_pass`
  - `semantic_pass`
  - `promotion_gate_result`

## Replay Pack And Attachment-Truth Doctrine (NEW v1.5)
- Prefer replayable scenario packs over ad hoc spot checks when a system has:
  - tool loops
  - grounded search
  - attachment-first document analysis
  - model-switch or finalizer behavior
- Required scenario families when those capabilities exist:
  - current-fact grounding
  - current-events briefing with required facets
  - contradictory search results
  - attachment-first summary
  - attachment follow-up expansion
  - model switch / helper finalizer path
  - no-visible-answer rescue
  - document verification partial
- Eval summaries should separate:
  - `trace_replay_pass`
  - `launched_artifact_pass`
  - `ui_truth_pass`
  - `overall_gate_result`
- Release gates should block when backend-only evals pass but launched-artifact or UI truth replay fails.

## Launched-Artifact Semantic Grounding Canaries (NEW v1.6)
- For grounded-answer systems, a built or launched artifact canary outranks backend-only confidence.
- When evaluating current-events, policy, legal, medical, or market-sensitive answers, require launched-artifact checks for:
  - `facet_coverage_pass`
  - `title_echo_pass`
  - `semantic_answer_pass`
  - `structured_output_pass`
  - `thin_coverage_honesty_pass`
- If a prompt demands a structured briefing, the canary should verify that each requested section contains either:
  1. grounded extracted claims, or
  2. a neutral thin-coverage disclosure
- Promotion must be blocked when the launched artifact:
  - repeats source titles instead of synthesizing claims
  - omits a required requested facet
  - emits a structurally correct but semantically empty answer

## Grounded-Briefing Eval Fields (NEW v1.6)
`eval_dataset.jsonl` and `eval_summary.json` should support:
- per-row `requested_facets[]`
- per-row `covered_facets[]`
- per-row `missing_facets[]`
- per-row `title_echo_detected`
- per-row `semantic_density_score`
- per-row `thin_coverage_honesty`
- summary `facet_coverage_rate`
- summary `title_echo_failures[]`
- summary `launched_artifact_semantic_pass`
