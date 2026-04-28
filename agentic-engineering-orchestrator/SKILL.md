---
name: agentic-engineering-orchestrator
description: Portable router for disciplined AI-assisted coding. Use when Codex must inspect repo reality before classifying risk, add explicit `risk_flags`, compare route options, preserve existing abstractions, distinguish observed work from inferred or planned work, and require validation artifacts before claiming software is understood, fixed, safe, or ready.
---

# Agentic Engineering Orchestrator

Convert raw software requests into evidence-driven execution with explicit truth status, route selection, and no-regression discipline.

Reference use:
- Read `references/routing-matrix.md` before finalizing `consult_plan` whenever risk is unclear, multiple specialists may apply, or ownership spans more than one domain.
- Read `references/worked-examples.md` when the request matches a known shape, artifact, or closure pattern.
- If the task depends on current versions, APIs, docs, release notes, policies, advisories, or benchmarks, retrieve current primary sources before making a recommendation.

Core principle:
- Do not confuse process with proof.
- Do not confuse planned work with completed work.
- Do not confuse new code with better code.
- Do not claim safe, ready, fixed, or understood without the matching artifact.

Truth-status rule:
Every non-trivial output must distinguish:
- `observed`: directly read, measured, executed, reproduced, or verified
- `inferred`: reasoned from observed evidence
- `planned`: proposed but not executed
- `blocked`: required evidence or action could not be obtained
- `simulated`: synthetic or hypothetical only when explicitly requested

Never present `inferred`, `planned`, `blocked`, or `simulated` work as `observed`.

## Protocol

### 0. Context sweep before routing
Inspect just enough repo and runtime reality to classify correctly before emitting the main intent artifact.

Minimum sweep targets when relevant:
- files or modules likely involved
- tests covering the touched behavior
- logs, traces, or incidents if behavior is failing
- current docs or release notes if currentness matters
- user-visible surfaces affected
- storage, memory, or runtime budgets if resource risk is plausible

Emit `ContextSweepV1`:
- `task_kind`
- `currentness_required`
- `repo_targets`
- `user_visible_surfaces`
- `initial_evidence`
- `unknowns`
- `blocked_inputs`
- `risk_flags_initial`

### 1. Emit `EngineeringIntentV1`
`EngineeringIntentV1` must contain:
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

Success criteria must be testable, and each one must later map to a validation step or evidence artifact.

### 2. Classify `risk_class`
- `low`: localized change, small blast radius, easy rollback
- `medium`: multiple files or interfaces, meaningful regression risk, or user-visible behavior change
- `high`: scale, security, money, data integrity, concurrency, critical-path behavior, or broad user-visible impact
- `critical`: active incident, severe outage, corruption, security exposure, or urgent production instability

Always add `risk_flags` in addition to `risk_class`.
Use one or more of:
- `architecture`
- `user_visible`
- `performance`
- `security`
- `appsec`
- `data_integrity`
- `concurrency`
- `compliance`
- `resource_budget`
- `currentness`
- `release_blocking`
- `incident`

### 3. Determine `task_kind`
Choose one primary `task_kind`:
- `analysis`
- `implementation`
- `validation`
- `incident`
- `experiment`
- `review`
- `policy`

### 4. Choose `work_mode`
- `fast_path`: low-risk work with enough observed evidence to proceed; requires `EngineeringIntentV1` and `UnderstandingReceiptV1` before implementation
- `guarded_path`: medium or high risk, incomplete evidence, or meaningful regression risk; requires the relevant specialist artifacts before implementation or release
- `critical_path`: route immediately to `$agentic-incident-triage-commander` and prioritize containment and restoration
- `review_only`: diagnosis, audit, or design only, no implementation unless explicitly escalated
- `validate_only`: tests, builds, runtime checks, or release verification only, no implementation unless a proven defect requires it

### 5. Emit `UnderstandingReceiptV1` before implementation or release signoff
`UnderstandingReceiptV1` must contain:
- `current_state`
- `desired_state`
- `delta`
- `assumptions`
- `open_questions`
- `evidence_used`
- `user_visible_impact`

Understanding is not complete until the `delta` is explicit.

### 6. Emit `EvidenceLedgerV1`
`EvidenceLedgerV1` must contain:
- `observed`
- `inferred`
- `unverified`
- `blocked`
- `sources`
- `truth_status_summary`

This artifact is mandatory whenever the task is medium+, currentness-sensitive, incident-related, or user-visible.

### 7. Route decision before coding
Compare at least two viable routes before implementation.
One route must explicitly consider extending or reusing existing logic.
One route must explicitly consider no code change, config-only change, test-only change, or routing-only change when plausible.

Emit `RouteDecisionV1`:
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

Route selection rules:
- prefer extending existing abstractions over creating parallel systems
- prefer test-only, config-only, or routing-only fixes when they solve the problem
- do not rewrite broad surfaces to fix a localized defect unless the current design is proven defective
- if two routes are close, choose lower regression risk and lower code churn
- never add a new subsystem without first explaining why the current abstraction cannot express the needed behavior

### 8. Existing logic preservation and no-regression protocol
Before editing:
- inspect the current logic, interfaces, tests, and user-visible behavior
- identify what already exists that partially solves the problem
- preserve public APIs and existing behavior unless change is required
- isolate risky behavior behind flags or narrow seams when practical
- create a rollback path for non-trivial changes
- do not delete, migrate, compact, or mutate user data without approval
- do not remove tests or safety checks to make a build pass

After editing:
- test the intended change
- test adjacent old behavior that could regress
- state what changed and what did not change

### 9. Specialist routing
Route by need, not by habit.
Use one lead specialist and only the adjunct specialists justified by `risk_flags`.

Lead and adjunct specialist rules:
- `$agentic-design-contract-architect` for medium/high-risk feature work, hidden architectural change, or contract drift
- `$agentic-understanding-receipt-enforcer` whenever explanation receipts are required or the current/desired delta is unclear
- `$agentic-performance-reality-guardian` for fanout, throughput, latency, cache, scale, render pressure, timer storms, event-loop pressure, or browser-entity budget risk
- `$agentic-production-readiness-gate` before closing any medium/high-risk delivery or incident repair
- `$agentic-innovation-experiment-bridge` for ambitious or exploratory ideas that need bounded experimentation
- `$qa-automation-engineer` for medium+ behavior changes, explicit acceptance checks, or regression risk
- `$principal_code_auditor_worldclass` for high-risk correctness, reliability, critical-path state transitions, or release-blocking regressions
- `$security-best-practices` when auth, authz, validation, secrets, sessions, crypto, or untrusted input boundaries change
- `$security_appsec_worldclass_auditor` when attack surface, privileged operations, sensitive data paths, uploads, rendering, or exploit suspicion is involved
- `$async-hygiene-monitor` when request, stream, job, worker, queue, or event-loop pressure may amplify failures
- `$thread-safety-auditor` when shared mutable state, races, dedupe, idempotency, or concurrency-sensitive retries are involved
- `$eval-flywheel-orchestrator` for experiment promotion decisions and regression-protected scoring
- `$skunkworks-innovation-strategist` for bold implementation options after the experiment is bounded
- `$skill-portability-guardian` before broadly distributing new or modified reusable skills

If a named specialist is not installed:
- keep the same `risk_class` and `work_mode`
- emit the missing consult explicitly
- inline that artifact contract yourself
- route to the closest existing safety net instead of silently downgrading the process

### 10. Performance override
If the failure signature is "slow, hot, janky, stalled, or unusable," treat it as a performance incident first, not a cosmetic issue.

Emit `PerformanceRealityV1`:
- `symptom_signature`
- `baseline_or_comparison`
- `suspected_hot_paths`
- `budgets_violated`
- `containment_options`
- `likely_amplifiers`
- `regression_checks`

Performance fallback priority:
- inline `PerformanceRealityV1`
- add `$qa-automation-engineer`
- add `$principal_code_auditor_worldclass` when correctness or critical-path behavior is exposed
- add `$async-hygiene-monitor` when timers, streams, workers, or event-loop pressure are plausible amplifiers

For render-heavy or browser-heavy incidents, prefer budget-first containment:
- visibility gating
- staged loading
- sampling
- throttling
- hot-loop inspection
- budget enforcement
before feature expansion

### 11. Currentness protocol
If the request depends on changing external reality:
- retrieve current primary sources first
- prefer official docs, release notes, advisories, standards, or regulator text
- compare multiple sources when practical
- downgrade confidence when primary evidence is unavailable
- do not answer current-software questions from stale memory when the answer could have changed

### 12. Resource and storage discipline
When build, model, artifact, dataset, or index growth is plausible, emit `ResourceImpactV1` before large operations.

`ResourceImpactV1`:
- `storage_impact`
- `memory_impact`
- `network_impact`
- `runtime_impact`
- `cache_paths`
- `cleanup_plan`
- `approval_needed`

Rules:
- do not trigger large downloads, model conversions, or artifact sprawl without a preflight
- do not duplicate compatible model assets or caches unnecessarily
- do not rely on repeated clean builds as a debugging strategy
- treat resource regressions as product regressions when they materially harm local workflows

### 13. Implementation discipline
When implementation is approved:
- make the smallest safe change
- keep the change scoped to the selected route
- preserve existing abstractions where possible
- do not silently widen scope
- do not silently change persistence or security boundaries
- do not claim execution you did not perform

### 14. Validation and closure
Before claiming anything is fixed, ready, safe, or understood, emit the required closure artifact.

`ValidationReceiptV1` must contain:
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

`ProductionReadinessGateV1` is required before closing:
- any medium or high-risk delivery
- any incident repair
- any user-visible behavior change with meaningful blast radius

`ProductionReadinessGateV1` must contain:
- `blocking_findings`
- `non_blocking_findings`
- `release_evidence`
- `rollback_readiness`
- `ship_recommendation`

Claim requirements:
- "understood" requires `EngineeringIntentV1` + `UnderstandingReceiptV1` + `EvidenceLedgerV1`
- "fixed" requires `ValidationReceiptV1` showing the defect path is resolved
- "safe" requires the relevant security, performance, or reliability artifacts
- "ready" requires `ValidationReceiptV1` + `ProductionReadinessGateV1` when applicable

### 15. Incident rule
If the task is an incident:
- restore service and contain blast radius before cleanup or elegance
- separate containment, diagnosis, and permanent fix
- keep evidence bounded and auditable
- do not expand features during incident handling unless containment requires it

### 16. Portability rule
Prefer portable outputs by default.
When the request is platform-specific, be explicit about the platform and keep the instructions scoped to that platform instead of pretending the answer is generic.

### 17. Final closure format
Close with:
- what was observed
- what was inferred
- what was changed
- what was validated
- what remains uncertain
- what specialist artifacts were produced
- why the selected route beat the alternatives

## Non-Negotiable Rules
- Keep velocity, but do not let speed skip reasoning.
- Keep outputs portable by default, but permit platform-specific guidance when the task is explicitly platform-specific.
- Prefer the lightest viable process for `low` risk and the strongest viable guardrails for `high` or `critical` risk.
- Inspect before editing.
- Reuse before rewriting.
- Validate before declaring success.
- Never blur observed work with planned work.
- Never claim safe, ready, fixed, or understood without the matching artifact.
