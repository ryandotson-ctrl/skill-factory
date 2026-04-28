# Readiness Checklist

## Minimum Evidence
- Coverage
  - regression test or explicit manual check
  - edge or failure path verification
- Telemetry
  - logs, metrics, traces, or health checks that expose failure
  - user-visible error semantics when degradation happens
- Rollback
  - safe revert, disable, or containment path
  - note any stateful cleanup needed
- Risk
  - top remaining risks
  - who or what is impacted if they occur
- Decision
  - clear `go` or `no_go`

## Stop Conditions
- No verification for a high-risk surface
- No rollback or containment path
- No observability on a failure mode you already expect
- No explicit owner for unresolved risk

## Skill Family Fit
- Use with `$qa-automation-engineer` for repeatable checks.
- Use with `$principal_code_auditor_worldclass` for high-risk review.
- Use with `$skill-portability-guardian` when the deliverable is a skill or reusable automation asset.
