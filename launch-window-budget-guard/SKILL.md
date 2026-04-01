---
name: launch-window-budget-guard
description: Portable launch gate that enforces time and cost budgets, preflight checks, and irreversible checklist policies before expensive runs.
metadata:
  version: 1.4.0
  short-description: Deterministic launch and budget gate enforcement
  portability_tier: strict_zero_leak
  scope: global
---

# Launch Window Budget Guard

## Use When
- You have a fixed run window or cost cap.
- Failure should happen early with explicit gate reasons.
- You need a repeatable go/no-go contract.

## Inputs
- `request.json` with:
- `budget` (`time_sec`, `cost_usd`)
- `forecast` (`time_sec`, `cost_usd`, optional `queue_time_sec`)
- `queue_forecast_sec` (optional override)
- `preflight_checks[]`
- `irreversible_template` (optional; e.g. `quantum_one_shot`)
- `irreversible_checks[]`
- `hard_stop_policy` (`block_on_warning`)

## Outputs
- `launch_contract.json`
- `launch_readiness_report.json`

## Features
- Queue-time-aware forecasting.
- Deterministic stop reasons.
- One-shot irreversible checklist templates.
- Staged launch policy support (`rehearsal -> confirmation -> guarded live launch`).
- Stop-on-pass policy for scarce paid-minute resources.
- Pre-quantum evidence floor checks (for example `classical_history_count` minimum).
- Drift-bias checklist hooks (require recheck/confirmation pass before paid launch).

## Additive Contract Notes (NEW v1.1)
For limited-minute quantum launches, readiness reports should include:
- `rehearsal_passed` (bool)
- `confirmation_passed` (bool)
- `stop_on_pass_enabled` (bool)

## Additive Contract Notes (NEW v1.2)
For hybrid optimization launches, readiness reports should include:
- `classical_evidence_floor_passed` (bool)
- `drift_guard_passed` (bool)
- `fallback_reason` when launch is blocked by reproducibility safeguards

## Additive Contract Notes (NEW v1.3)
For queue-pressure-aware launch governance:
- readiness report should include `recommended_action` (`launch_now|defer_and_recheck|abort`)
- readiness report should include `retry_recommendation` (`eligible`, `reason`, `recheck_after_sec`, `max_rechecks`, `remaining_rechecks`)
- launch contract should include normalized `queue_policy` used for deterministic defer/recheck behavior

## Additive Contract Notes (NEW v1.4)
For quantum comparative launch governance:
- contracts should include `launch_mode` (`standard|near_miss|success_comparison`)
- contracts should include `launch_policy` (`stop_on_pass_enabled`, `planned_paid_runs`, `max_paid_runs`)
- readiness should enforce `stop_on_pass_required_for_success_comparison` as a hard check
- readiness should enforce `paid_run_plan_within_limit` as a hard check

## Run
```bash
python3 scripts/guard.py --request request.json --out-dir out
```

## Validation
```bash
python3 scripts/guard.py --self-test
```

## References
- `references/contracts-v1.md`
