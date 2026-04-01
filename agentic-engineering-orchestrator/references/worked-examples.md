# Worked Examples

Use these as canonical route outputs when the user request resembles one of the common trigger shapes.

## Build Search Autocomplete
```text
EngineeringIntentV1
- goal: Build autocomplete that feels fast without overwhelming backend search resources.
- scope: UI keystroke handling, backend search fanout, and regression coverage for the request path.
- risk_class: high
- work_mode: guarded_path
- constraints: avoid per-keystroke expensive work, preserve existing search relevance, keep the change reversible.
- success_criteria: debounce or coalescing is explicit, backend fanout is bounded, telemetry can show query rate and latency, regression checks exist.
- consult_plan:
  - $agentic-design-contract-architect
  - $agentic-performance-reality-guardian
  - $qa-automation-engineer
```

## Refactor Auth Middleware
```text
EngineeringIntentV1
- goal: Improve middleware structure without weakening authentication or authorization behavior.
- scope: request auth path, session or token validation, boundary checks, and release verification.
- risk_class: high
- work_mode: guarded_path
- constraints: preserve security semantics, avoid user lockouts, maintain rollback clarity.
- success_criteria: security invariants are explicit, regression coverage exists for allowed and denied flows, rollout signals and rollback path are named.
- consult_plan:
  - $agentic-design-contract-architect
  - $security-best-practices
  - $principal_code_auditor_worldclass
  - $agentic-production-readiness-gate
```

## Fix A Race Condition In Payment Retries
```text
EngineeringIntentV1
- goal: Stop duplicate or inconsistent payment retry behavior and restore deterministic state transitions.
- scope: retry coordination, shared state, idempotency boundaries, and incident-safe validation.
- risk_class: critical
- work_mode: critical_path
- constraints: protect money movement, prefer safe mitigation first, verify recovery before cleanup.
- success_criteria: the race is contained, recovery is observable, the durable fix is verified against repeat retries.
- consult_plan:
  - $agentic-incident-triage-commander
  - $thread-safety-auditor
  - $async-hygiene-monitor
  - $qa-automation-engineer
  - $agentic-production-readiness-gate
```

## Give Me A Bold Agentic Feature Idea
```text
ExperimentBridgeV1
- hypothesis: A bounded agentic capability can improve user value without sacrificing reliability or debuggability.
- blast_radius: Limit the experiment to an isolated path, feature flag, or non-critical workflow.
- eval_plan: Compare against a baseline with explicit success and regression criteria.
- promotion_criteria: Promote only if the eval is repeatable, rollback is clear, and readiness follow-up is named.

consult_plan:
  - $agentic-innovation-experiment-bridge
  - $skunkworks-innovation-strategist
  - $eval-flywheel-orchestrator
```

## Add A Small CLI Flag
```text
EngineeringIntentV1
- goal: Add a localized CLI flag without changing unrelated behavior.
- scope: argument parsing, help text, and one targeted execution path.
- risk_class: low
- work_mode: fast_path
- constraints: keep backward compatibility, avoid hidden side effects.
- success_criteria: flag behavior is explicit, existing defaults remain unchanged, a short understanding receipt explains the change.
- consult_plan:
  - $agentic-understanding-receipt-enforcer
```

## The App Became Slow After A Feature Pass
```text
EngineeringIntentV1
- goal: Restore usability and contain the regression before doing more feature polish.
- scope: hot render loops, timer cadence, hidden-layer work, fanout, and the smallest safe mitigation that returns interactivity.
- risk_class: high
- work_mode: guarded_path
- constraints: keep recently added user-facing behavior where possible, prefer reversible budget-first containment, and verify the live surface after the fix.
- success_criteria: the app is responsive again, hidden layers do not burn resources, the hottest path has an explicit guard, and regression proof covers the repaired failure mode.
- consult_plan:
  - $agentic-performance-reality-guardian
  - $qa-automation-engineer
  - $principal_code_auditor_worldclass

PerformanceRealityV1
- load_shape: Identify entity counts, particle fanout, render cadence, polling intervals, and any work still happening while the layer is hidden.
- amplifiers: Full-catalog rendering, request storms, requestAnimationFrame loops, repeated DOM rebuilds, and data structures with avoidable linear scans.
- guards: Visibility gating, sampling, staged loading, throttled updates, capped budgets, and timer reductions.
- observability: Compare before and after with concrete counts, refresh rates, and user-visible responsiveness evidence.
- budget_first_mitigation: Restore usability first; only then re-expand density or fidelity if evidence supports it.

fallback_if_performance_specialist_missing:
  - inline PerformanceRealityV1
  - add $qa-automation-engineer
  - add $async-hygiene-monitor when event-loop or timer pressure is plausible
```

## Production Is Down
```text
IncidentTriageV1
- symptom: Users cannot complete the critical path and the system is actively degraded.
- likely_causes: recent release or config drift, overload, dependency failure, or concurrency collapse.
- evidence_needed: current blast radius, recent changes, runtime pressure signals, and recovery confirmation.
- safe_mitigation: choose the fastest reversible action that protects users and data.
- next_fix: capture the durable repair, required consults, and readiness follow-up after stabilization.

consult_plan:
  - $agentic-incident-triage-commander
  - relevant specialist based on the observed failure signature
  - $agentic-production-readiness-gate before closure
```
