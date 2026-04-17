---
name: quantum-proof-assurance-gate
description: Deterministic launch assurance gate that combines invariants, gradient
  checks, and budget proofs into a single go or no-go contract for one-shot quantum
  runs.
metadata:
  version: 1.1.0
  short-description: One-shot quantum proof and launch assurance gate
  portability_tier: strict_zero_leak
  scope: global
  requires_env: []
  project_profiles: []
---

# Quantum Proof Assurance Gate

## Use When
- Quantum launch budget is strict and failures are expensive.
- You need a deterministic go/no-go policy backed by evidence artifacts.
- You want one contract that combines invariants, gradients, and budget limits.

## Inputs
- `request.json` with invariants, gradient checks, and budget evidence.

## Outputs
- `proof_artifact.json`
- `launch_contract.json`

## Additive Contract Notes (NEW v1.1)
For post-success comparative quantum launches, contracts should include:
- `mode` (`near_miss|success_comparison`)
- `stop_on_pass_guard` as a hard check for `success_comparison`
- `paid_run_budget_guard` to enforce one-shot (or configured) paid-run limits
- `mock_provenance_guard` proving mock runtime evidence is not counted as paid usage

## Run
```bash
python3 scripts/prove_launch.py --request request.json --out-dir out
```

## Validation
```bash
python3 scripts/prove_launch.py --self-test
```

## References
- `references/contracts-v1.md`
