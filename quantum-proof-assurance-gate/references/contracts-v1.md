# Proof Assurance Contracts V1

## ProofArtifactV1

```json
{
  "schema": "ProofArtifactV1",
  "launch_mode": "near_miss|success_comparison",
  "invariants": [
    {"name": "string", "pass": true, "evidence_hash": "sha256"}
  ],
  "gradient_checks": [
    {"target": "string", "abs_err": 0.0, "rel_err": 0.0, "tolerance": 0.0, "pass": true}
  ],
  "evidence_provenance": {
    "mock_runtime_runs": 0,
    "real_runtime_runs": 0,
    "mock_counts_toward_paid_budget": false
  },
  "comparison_guard": {"classical_success_gate_pass": true},
  "budget_proof": {
    "pass": true,
    "time_sec": 0.0,
    "cost_usd": 0.0,
    "stop_on_pass_enabled": true,
    "planned_paid_runs": 1,
    "max_paid_runs": 1
  }
}
```

## LaunchGateV1

```json
{
  "schema": "LaunchGateV1",
  "go": true,
  "mode": "near_miss|success_comparison",
  "checks": [
    {"name": "string", "passed": true, "detail": "string", "severity": "info|warning|error"}
  ],
  "launch_policy": {
    "stop_on_pass_enabled": true,
    "planned_paid_runs": 1,
    "max_paid_runs": 1
  },
  "evidence_provenance": {
    "mock_runtime_runs": 0,
    "real_runtime_runs": 0,
    "mock_counts_toward_paid_budget": false
  },
  "budget": {"time_sec": 0, "cost_usd": 0.0},
  "stop_reason": "string"
}
```
