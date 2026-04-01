# Routing Matrix

## Shared Enums
- `RiskClass`: `low | medium | high | critical`
- `WorkMode`: `fast_path | guarded_path | critical_path`

## Canonical Artifacts
- `EngineeringIntentV1`
  - `goal`
  - `scope`
  - `risk_class`
  - `work_mode`
  - `constraints`
  - `success_criteria`
  - `consult_plan`
- `DesignContractV1`
  - `approach`
  - `interfaces`
  - `invariants`
  - `failure_modes`
  - `acceptance_checks`
- `UnderstandingReceiptV1`
  - `why_this_works`
  - `what_could_break`
  - `how_to_debug`
  - `unknowns`
- `PerformanceRealityV1`
  - `load_shape`
  - `amplifiers`
  - `guards`
  - `observability`
  - `budget_first_mitigation`
- `ReadinessGateV1`
  - `coverage`
  - `telemetry`
  - `rollback`
  - `release_risks`
  - `go_no_go`
- `IncidentTriageV1`
  - `symptom`
  - `likely_causes`
  - `evidence_needed`
  - `safe_mitigation`
  - `next_fix`
- `ExperimentBridgeV1`
  - `hypothesis`
  - `blast_radius`
  - `eval_plan`
  - `promotion_criteria`

## Routing Policy
- `low`
  - `work_mode`: `fast_path`
  - required artifacts: `EngineeringIntentV1`, `UnderstandingReceiptV1`
- `medium`
  - `work_mode`: `guarded_path`
  - required artifacts: `EngineeringIntentV1`, `DesignContractV1`, `UnderstandingReceiptV1`
  - typical consults: `$qa-automation-engineer`
- `high`
  - `work_mode`: `guarded_path`
  - required artifacts: `EngineeringIntentV1`, `DesignContractV1`, `UnderstandingReceiptV1`, `PerformanceRealityV1`, `ReadinessGateV1`
  - typical consults: `$qa-automation-engineer`, `$principal_code_auditor_worldclass`
- `critical`
  - `work_mode`: `critical_path`
  - immediate route: `$agentic-incident-triage-commander`
  - closure requirement: `ReadinessGateV1`

## Deterministic Consult Routing
- Add `$qa-automation-engineer` when acceptance checks touch behavior, failure semantics, or regressions matter.
- Add `$principal_code_auditor_worldclass` when correctness, reliability, schema or contract drift, data integrity, or critical-path state transitions are at risk.
- Add `$security-best-practices` when auth, authz, validation, secrets, sessions, crypto, tenant boundaries, or untrusted input handling changed.
- Add `$security_appsec_worldclass_auditor` when the change expands externally reachable attack surface, privileged operations, code execution, uploads, rendering of untrusted content, sensitive data flows, or exploit suspicion.
- Add `$async-hygiene-monitor` when request, stream, job, or worker paths may block the event loop, deadlock, or collapse under queue or retry pressure.
- Add a performance consult when the failure signature includes slowness, heat, browser jank, render overload, timer storms, exploding entity counts, or hidden work on non-visible layers.
- Add `$thread-safety-auditor` when shared mutable state, lockless concurrency, race-sensitive retries, dedupe, or idempotency guarantees are involved.
- Add `$skill-portability-guardian` when the deliverable is a new or modified reusable skill.
- Add `$eval-flywheel-orchestrator` when an experiment or optimization needs promotion evidence or regression-protected scoring.
- Add `$skunkworks-innovation-strategist` only after an exploratory idea is bounded through `$agentic-innovation-experiment-bridge`.

## Missing Specialist Fallback
- If the ideal specialist is unavailable, do not downgrade risk or skip the artifact.
- Inline the missing artifact contract in the answer and add the nearest installed safety nets.
- For missing performance specialist coverage:
  - require `PerformanceRealityV1`
  - add `$qa-automation-engineer`
  - add `$principal_code_auditor_worldclass` when correctness or release risk is also present
  - add `$async-hygiene-monitor` when timers, workers, polling, streams, or event-loop pressure may amplify the issue
- Performance incidents should bias toward containment first:
  - reduce fanout
  - cap budgets
  - gate hidden work
  - slow polling or animation cadence
  - verify before re-expanding scope

## Special Route
- Innovation or exploratory ideas:
  - start with `$agentic-innovation-experiment-bridge`
  - then use `$skunkworks-innovation-strategist`
  - then use `$eval-flywheel-orchestrator`

## Trigger Examples
- "Build search autocomplete"
  - router -> design contract -> performance guardian -> QA
- "Refactor auth middleware"
  - router -> design contract -> `$security-best-practices` -> `$principal_code_auditor_worldclass` -> readiness gate
- "Fix a race condition in payment retries"
  - incident triage -> `$thread-safety-auditor` and `$async-hygiene-monitor` -> QA -> readiness gate
- "Give me a bold agentic feature idea"
  - innovation bridge -> skunkworks -> eval
- "Add a small CLI flag"
  - stay in `fast_path` unless the flag changes critical behavior
- "The app got very slow after a feature pass"
  - route as `high` by default
  - require `PerformanceRealityV1`
  - consult performance specialist or fallback safety nets
  - contain render/load pressure before feature polish
- "Production is down"
  - route immediately to incident triage
