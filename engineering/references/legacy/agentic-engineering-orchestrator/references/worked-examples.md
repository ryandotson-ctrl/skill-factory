# Worked Examples

Use these as canonical route outputs when the user request resembles one of the common trigger shapes.

## Build Search Autocomplete
```text
ContextSweepV1
- task_kind: implementation
- currentness_required: no
- repo_targets: search UI keystroke handler, backend query path, existing autocomplete or debounce helpers
- user_visible_surfaces: search box, suggestion list, request latency perceived by the user
- initial_evidence: current search flow and fanout points have been inspected
- unknowns: current debounce policy, telemetry coverage, backend rate limits
- blocked_inputs: none
- risk_flags_initial: user_visible, performance, release_blocking

EngineeringIntentV1
- goal: Build autocomplete that feels fast without overwhelming backend search resources.
- scope: UI keystroke handling, backend search fanout, and regression coverage for the request path.
- non_goals: changing ranking semantics or redesigning the entire search surface
- risk_class: high
- risk_flags: user_visible, performance, release_blocking
- work_mode: guarded_path
- constraints: avoid per-keystroke expensive work, preserve existing search relevance, keep the change reversible.
- success_criteria: debounce or coalescing is explicit, backend fanout is bounded, telemetry can show query rate and latency, regression checks exist.
- consult_plan:
  - $agentic-design-contract-architect
  - $agentic-performance-reality-guardian
  - $qa-automation-engineer

RouteDecisionV1
- option_a: extend the existing search request path with debounce and bounded fanout
- option_b: add a separate autocomplete subsystem with its own fetch pipeline
- option_c_optional: no code change, only increase backend capacity
- selected_route: option_a
- why_selected: lowest churn and reuses existing search abstractions while addressing the actual fanout risk
- why_rejected: option_b creates a parallel system; option_c hides the problem instead of containing it
- existing_logic_to_reuse: current search request orchestration and result rendering path
- regression_risk: medium
- code_churn: low_to_medium
- rollback_plan: revert debounce and bounded fanout changes behind a narrow seam
```

## Refactor Auth Middleware
```text
ContextSweepV1
- task_kind: implementation
- currentness_required: yes
- repo_targets: auth middleware, token/session validation code, route guards, current auth docs or release notes
- user_visible_surfaces: login state, authorized vs denied flows, session continuity
- initial_evidence: current auth path and user-facing flows have been inspected
- unknowns: token refresh edge cases, undocumented middleware ordering constraints
- blocked_inputs: none
- risk_flags_initial: security, appsec, user_visible, currentness, release_blocking

EngineeringIntentV1
- goal: Improve middleware structure without weakening authentication or authorization behavior.
- scope: request auth path, session or token validation, boundary checks, and release verification.
- non_goals: changing product auth semantics or widening privileged access
- risk_class: high
- risk_flags: security, appsec, user_visible, currentness, release_blocking
- work_mode: guarded_path
- constraints: preserve security semantics, avoid user lockouts, maintain rollback clarity.
- success_criteria: security invariants are explicit, regression coverage exists for allowed and denied flows, rollout signals and rollback path are named.
- consult_plan:
  - $agentic-design-contract-architect
  - $security-best-practices
  - $principal_code_auditor_worldclass
  - $agentic-production-readiness-gate

EvidenceLedgerV1
- observed: middleware order, current allow/deny behavior, current auth boundary code, current official auth docs
- inferred: the refactor is safe only if middleware ordering and token/session invariants remain unchanged
- unverified: edge-case refresh behavior until tests and runtime checks run
- blocked: none
- sources: repo code, tests, current official docs
- truth_status_summary: observed plus inferred; no planned work presented as done
```

## Fix A Race Condition In Payment Retries
```text
ContextSweepV1
- task_kind: incident
- currentness_required: no
- repo_targets: retry coordinator, payment state transitions, idempotency logic, retry tests, incident logs
- user_visible_surfaces: duplicate charges, failed retries, inconsistent payment status
- initial_evidence: defect path has been reproduced or evidenced from logs
- unknowns: exact timing window under production concurrency
- blocked_inputs: any missing logs or replay artifacts
- risk_flags_initial: incident, data_integrity, concurrency, release_blocking, user_visible

EngineeringIntentV1
- goal: Stop duplicate or inconsistent payment retry behavior and restore deterministic state transitions.
- scope: retry coordination, shared state, idempotency boundaries, and incident-safe validation.
- non_goals: feature expansion or broad retry-system redesign during containment
- risk_class: critical
- risk_flags: incident, data_integrity, concurrency, release_blocking, user_visible
- work_mode: critical_path
- constraints: protect money movement, prefer safe mitigation first, verify recovery before cleanup.
- success_criteria: the race is contained, recovery is observable, the durable fix is verified against repeat retries.
- consult_plan:
  - $agentic-incident-triage-commander
  - $thread-safety-auditor
  - $async-hygiene-monitor
  - $qa-automation-engineer
  - $agentic-production-readiness-gate

RouteDecisionV1
- option_a: extend existing retry coordination with explicit idempotency guard and narrow concurrency fix
- option_b: replace retry subsystem
- option_c_optional: config-only containment that disables retries temporarily
- selected_route: option_a after containment
- why_selected: fastest durable fix with the smallest blast radius
- why_rejected: option_b is too large for an incident; option_c may be used only for immediate containment
- existing_logic_to_reuse: current retry coordinator and state transition model
- regression_risk: high
- code_churn: medium
- rollback_plan: revert the narrow fix and keep the containment toggle available
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
ContextSweepV1
- task_kind: implementation
- currentness_required: no
- repo_targets: existing CLI parser, help text, one targeted execution path, nearby flag tests
- user_visible_surfaces: CLI help and the targeted command behavior
- initial_evidence: current parser and defaults have been inspected
- unknowns: whether existing shorthand aliases collide
- blocked_inputs: none
- risk_flags_initial: architecture

EngineeringIntentV1
- goal: Add a localized CLI flag without changing unrelated behavior.
- scope: argument parsing, help text, and one targeted execution path.
- non_goals: CLI redesign or default behavior changes
- risk_class: low
- risk_flags: architecture
- work_mode: fast_path
- constraints: keep backward compatibility, avoid hidden side effects.
- success_criteria: flag behavior is explicit, existing defaults remain unchanged, a short understanding receipt explains the change.
- consult_plan:
  - $agentic-understanding-receipt-enforcer

RouteDecisionV1
- option_a: extend the existing parser and targeted path
- option_b: add a new command wrapper
- option_c_optional: test-only clarification if behavior already exists
- selected_route: option_a
- why_selected: smallest safe change and best reuse of existing logic
- why_rejected: option_b adds unnecessary surface area; option_c is only valid if the feature already exists
- existing_logic_to_reuse: current parser and targeted execution path
- regression_risk: low
- code_churn: low
- rollback_plan: revert the single parser and targeted path change
```

## The App Became Slow After A Feature Pass
```text
ContextSweepV1
- task_kind: incident
- currentness_required: no
- repo_targets: hot render path, timer loops, worker or stream pressure, recent changed files, related regression tests
- user_visible_surfaces: jank, heat, sluggish interaction, frozen or delayed renders
- initial_evidence: recent regression path and live symptom signature have been inspected
- unknowns: exact hottest path until profiling or concrete traces are reviewed
- blocked_inputs: profiler or trace data if not yet available
- risk_flags_initial: performance, user_visible, release_blocking, resource_budget

EngineeringIntentV1
- goal: Restore usability and contain the regression before doing more feature polish.
- scope: hot render loops, timer cadence, hidden-layer work, fanout, and the smallest safe mitigation that returns interactivity.
- non_goals: visual redesign or feature expansion during containment
- risk_class: high
- risk_flags: performance, user_visible, release_blocking, resource_budget
- work_mode: guarded_path
- constraints: keep recently added user-facing behavior where possible, prefer reversible budget-first containment, and verify the live surface after the fix.
- success_criteria: the app is responsive again, hidden layers do not burn resources, the hottest path has an explicit guard, and regression proof covers the repaired failure mode.
- consult_plan:
  - $agentic-performance-reality-guardian
  - $qa-automation-engineer
  - $principal_code_auditor_worldclass

PerformanceRealityV1
- symptom_signature: app is slow, hot, and difficult to use after a feature pass
- baseline_or_comparison: compare current interaction latency and heat to the last known good path
- suspected_hot_paths: render loops, timer cadence, hidden-layer work, request fanout, repeated DOM rebuilds
- budgets_violated: responsiveness, render pressure, local resource budget
- containment_options: visibility gating, staged loading, sampling, throttling, hot-loop inspection
- likely_amplifiers: requestAnimationFrame loops, polling storms, repeated rebuilds, avoidable linear scans
- regression_checks: verify restored interactivity and check adjacent user-visible flows

ValidationReceiptV1
- files_read: hot render path, recent changed files, existing regression tests
- files_changed: the smallest safe mitigation set
- commands_run: profiling, targeted checks, and regression commands actually executed
- tests_run: intended regression checks plus adjacent old behavior checks
- runtime_checks: live interaction and heat verification
- user_visible_checks: responsive rendering and restored usability
- results: regression path contained and validated
- remaining_risks: any deferred re-expansion or unprofiled edge case
- resource_impact: reduced hidden work and tighter render budget
- truth_status: observed and validated
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
