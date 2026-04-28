# Portable Contracts V1

These contracts are portability-safe, vendor-agnostic, and intended for cross-project reuse.

## ExecutionModeV1

```json
{
  "schema": "ExecutionModeV1",
  "mode": "full|limited|disabled",
  "reason": "string",
  "fallback_modes": ["string"],
  "provider": "string",
  "checked_at": "ISO-8601 timestamp",
  "provenance": [
    {"name": "string", "passed": true, "detail": "string"}
  ]
}
```

## DeviceRouteV1

```json
{
  "schema": "DeviceRouteV1",
  "mode": "sim|ibm|cirq",
  "provider": "string",
  "backend": "string",
  "deterministic": true,
  "shots": 0,
  "credential_state": "ready|missing|invalid|not_required"
}
```

## LaunchGateV1

```json
{
  "schema": "LaunchGateV1",
  "go": true,
  "checks": [
    {
      "name": "string",
      "passed": true,
      "detail": "string",
      "severity": "info|warning|error"
    }
  ],
  "budget": {
    "time_sec": 0,
    "cost_usd": 0.0
  },
  "stop_reason": "string"
}
```

## CompatibilityV1

```json
{
  "schema": "CompatibilityV1",
  "target": "string",
  "artifact": "string",
  "required_capabilities": ["string"],
  "missing_capabilities": ["string"],
  "auto_fixes": ["string"]
}
```

## RunLedgerEntryV1

```json
{
  "schema": "RunLedgerEntryV1",
  "run_id": "string",
  "stage": "string",
  "config_hash": "sha256",
  "inputs_hash": "sha256",
  "outputs_hash": "sha256",
  "status": "ok|error|skipped|timeout",
  "error_code": "string|null",
  "ts": "ISO-8601 timestamp",
  "prev_hash": "sha256|GENESIS",
  "entry_hash": "sha256"
}
```

## EvalResultV1

```json
{
  "schema": "EvalResultV1",
  "dataset_id": "string",
  "grader_id": "string",
  "score": 0.0,
  "threshold": 0.0,
  "regression_delta": 0.0,
  "pass": true,
  "gradient_pass": true,
  "speed_gain_pct": 0.0,
  "quality_drop_pct": 0.0,
  "frontier_class": "near_miss_frontier|success_frontier|below_frontier|quality_risk_frontier|unknown_frontier",
  "stochastic_mean": 0.0,
  "stochastic_ci_half_width": 0.0
}
```

## TelemetryConformanceV1

```json
{
  "schema": "TelemetryConformanceV1",
  "resource_attrs": ["string"],
  "trace_attrs": ["string"],
  "metric_attrs": ["string"],
  "violations": ["string"],
  "pass": true,
  "redaction_policy": {
    "quantum_job_id_redaction_required": true,
    "raw_job_id_violations": 0
  }
}
```

## QuantumOpSpecV1

```json
{
  "schema": "QuantumOpSpecV1",
  "n_qubits": 2,
  "ansatz_id": "string",
  "diff_method": "parameter-shift|adjoint",
  "shots": 0,
  "trainable_params": 2
}
```

## ProofArtifactV1

```json
{
  "schema": "ProofArtifactV1",
  "invariants": [
    {"name": "string", "pass": true, "evidence_hash": "sha256"}
  ],
  "gradient_checks": [
    {"target": "string", "abs_err": 0.0, "rel_err": 0.0, "tolerance": 0.0, "pass": true}
  ],
  "budget_proof": {"pass": true, "time_sec": 0.0, "cost_usd": 0.0}
}
```
