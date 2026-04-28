# Routing Matrix

## Shared Enums
- `RiskClass`: `low | medium | high | critical`
- `RiskFlag`: `architecture | user_visible | performance | security | appsec | data_integrity | concurrency | compliance | resource_budget | currentness | release_blocking | incident`
- `TaskKind`: `analysis | implementation | validation | incident | experiment | review | policy`
- `WorkMode`: `fast_path | guarded_path | critical_path | review_only | validate_only`

## Canonical Artifacts
- `ContextSweepV1`
  - `task_kind`
  - `currentness_required`
  - `repo_targets`
  - `user_visible_surfaces`
  - `initial_evidence`
  - `unknowns`
  - `blocked_inputs`
  - `risk_flags_initial`
- `EngineeringIntentV1`
  - `goal`
  - `scope`
  - `non_goals`
  - `risk_class`
  - `risk_flags`
  - `work_mode`
  - `constraints`
  - `approval_boundaries`
  - `success_criteria`
  - `consult_plan`
- `UnderstandingReceiptV1`
  - `current_state`
  - `desired_state`
  - `delta`
  - `assumptions`
  - `open_questions`
  - `evidence_used`
  - `user_visible_impact`
- `EvidenceLedgerV1`
  - `observed`
  - `inferred`
  - `unverified`
  - `blocked`
  - `sources`
  - `truth_status_summary`
- `RouteDecisionV1`
  - `option_a`
  - `option_b`
  - `option_c_optional`
  - `selected_route`
  - `why_selected`
  - `why_rejected`
  - `existing_logic_to_reuse`
  - `regression_risk`
  - `code_churn`
  - `rollback_plan`
- `DesignContractV1`
  - `approach`
  - `interfaces`
  - `invariants`
  - `failure_modes`
  - `acceptance_checks`
- `PerformanceRealityV1`
  - `symptom_signature`
  - `baseline_or_comparison`
  - `suspected_hot_paths`
  - `budgets_violated`
  - `containment_options`
  - `likely_amplifiers`
  - `regression_checks`
- `ResourceImpactV1`
  - `storage_impact`
  - `memory_impact`
  - `network_impact`
  - `runtime_impact`
  - `cache_paths`
  - `cleanup_plan`
  - `approval_needed`
- `ValidationReceiptV1`
  - `files_read`
  - `files_changed`
  - `commands_run`
  - `tests_run`
  - `runtime_checks`
  - `user_visible_checks`
  - `results`
  - `remaining_risks`
  - `resource_impact`
  - `truth_status`
- `ProductionReadinessGateV1`
  - `blocking_findings`
  - `non_blocking_findings`
  - `release_evidence`
  - `rollback_readiness`
  - `ship_recommendation`
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
  - minimum truth state: `ContextSweepV1`
  - `work_mode`: `fast_path`
  - required artifacts: `EngineeringIntentV1`, `UnderstandingReceiptV1`
- `medium`
  - minimum truth state: `ContextSweepV1`, `EvidenceLedgerV1`
  - `work_mode`: `guarded_path`
  - required artifacts: `EngineeringIntentV1`, `UnderstandingReceiptV1`, `EvidenceLedgerV1`, `RouteDecisionV1`, `DesignContractV1`
  - typical consults: `$qa-automation-engineer`
- `high`
  - minimum truth state: `ContextSweepV1`, `EvidenceLedgerV1`
  - `work_mode`: `guarded_path`
  - required artifacts: `EngineeringIntentV1`, `UnderstandingReceiptV1`, `EvidenceLedgerV1`, `RouteDecisionV1`, `DesignContractV1`, `PerformanceRealityV1`, `ValidationReceiptV1`, `ProductionReadinessGateV1`
  - typical consults: `$qa-automation-engineer`, `$principal_code_auditor_worldclass`
- `critical`
  - minimum truth state: `ContextSweepV1`, `EvidenceLedgerV1`
  - `work_mode`: `critical_path`
  - immediate route: `$agentic-incident-triage-commander`
  - closure requirement: `ValidationReceiptV1`, `ProductionReadinessGateV1`

## Route Decision Rules
- Compare at least two viable routes before implementation.
- One route must consider extending or reusing existing logic.
- One route must consider no code change, config-only, test-only, or routing-only remediation when plausible.
- Prefer lower regression risk and lower churn when routes are close.
- Never add a parallel subsystem without explaining why the current abstraction cannot express the needed behavior.

## No-Regression Protocol
- Inspect current logic, interfaces, tests, and user-visible behavior before editing.
- Preserve public APIs and existing behavior unless change is required.
- Keep rollback explicit for non-trivial changes.
- Do not remove tests or safety checks to make a build pass.
- After editing, test both the intended change and adjacent old behavior that could regress.

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
- Add current-primary-source retrieval when `currentness` risk is present.

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

## Claim Requirements
- "understood" requires `EngineeringIntentV1` + `UnderstandingReceiptV1` + `EvidenceLedgerV1`
- "fixed" requires `ValidationReceiptV1` showing the defect path is resolved
- "safe" requires the relevant security, performance, or reliability artifacts
- "ready" requires `ValidationReceiptV1` + `ProductionReadinessGateV1` when applicable

## Special Route
- Innovation or exploratory ideas:
  - start with `$agentic-innovation-experiment-bridge`
  - then use `$skunkworks-innovation-strategist`
  - then use `$eval-flywheel-orchestrator`

## Trigger Examples
- "Build search autocomplete"
  - context sweep -> route decision -> design contract -> performance guardian -> QA
- "Refactor auth middleware"
  - context sweep -> route decision -> design contract -> `$security-best-practices` -> `$principal_code_auditor_worldclass` -> production readiness gate
- "Fix a race condition in payment retries"
  - incident triage -> `$thread-safety-auditor` and `$async-hygiene-monitor` -> QA -> production readiness gate
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
