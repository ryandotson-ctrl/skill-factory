---
name: agentic-engineering-orchestrator
description: Portable router for disciplined AI-assisted coding. Use when Codex is asked to implement, refactor, debug, review, or design software changes and must classify risk, choose `fast_path`, `guarded_path`, or `critical_path`, require understanding and readiness receipts, and route to the right specialist skills without sacrificing speed.
---

# Agentic Engineering Orchestrator

Convert raw software requests into evidence-driven execution.

Read `references/routing-matrix.md` whenever risk is not obvious or multiple specialists may apply. Read `references/worked-examples.md` when you need canonical example outputs for common request shapes.

## Workflow
1. Emit `EngineeringIntentV1` with:
   - `goal`
   - `scope`
   - `risk_class`
   - `work_mode`
   - `constraints`
   - `success_criteria`
   - `consult_plan`
2. Classify `risk_class`:
   - `low`: localized change, small blast radius, easy rollback.
   - `medium`: multiple files or interfaces, meaningful regression risk.
   - `high`: scale, security, money, data integrity, concurrency, or critical-path behavior.
   - `critical`: active incident, severe outage, corruption, or urgent production instability.
3. Choose `work_mode`:
   - `fast_path`: require `EngineeringIntentV1` plus `UnderstandingReceiptV1`.
   - `guarded_path`: require the relevant specialist artifacts before implementation or release.
   - `critical_path`: route immediately to `$agentic-incident-triage-commander`.
4. Route by need:
   - `$agentic-design-contract-architect` for medium/high-risk feature work or hidden architectural change.
   - `$agentic-understanding-receipt-enforcer` whenever explanation receipts are required.
   - `$agentic-performance-reality-guardian` for fanout, throughput, latency, cache, scale, render pressure, timer storms, or browser-entity budget risk.
   - `$agentic-production-readiness-gate` before closing medium/high-risk delivery or incident repair.
   - `$agentic-innovation-experiment-bridge` for ambitious or exploratory ideas.
5. Reuse existing specialists by name instead of duplicating them:
   - `$qa-automation-engineer` for medium+ behavior changes, explicit acceptance checks, or regression risk.
   - `$principal_code_auditor_worldclass` for high-risk correctness, reliability, contract drift, critical-path state transitions, or release-blocking regressions.
   - `$security-best-practices` when auth, authz, validation, secrets, sessions, crypto, or untrusted input boundaries changed.
   - `$security_appsec_worldclass_auditor` when attack surface, privileged operations, sensitive data paths, uploads, rendering, or exploit suspicion is involved.
   - `$async-hygiene-monitor` when request, stream, job, or worker logic may block or collapse under load.
   - `$thread-safety-auditor` when shared mutable state, races, dedupe, idempotency, or concurrency-sensitive retries are involved.
   - `$eval-flywheel-orchestrator` for experiment promotion decisions and regression-protected scoring.
   - `$skunkworks-innovation-strategist` for bold implementation options after an experiment is bounded.
   - `$skill-portability-guardian` before broadly distributing new or modified reusable skills.
6. If a named specialist is not installed:
   - keep the same `risk_class` and `work_mode`;
   - emit the missing consult explicitly;
   - inline the missing artifact contract yourself;
   - route to the closest existing safety net instead of silently downgrading the process.
   Performance fallback priority:
   - inline `PerformanceRealityV1`
   - add `$qa-automation-engineer`
   - add `$principal_code_auditor_worldclass` when correctness or critical-path behavior is exposed
   - add `$async-hygiene-monitor` when timers, streams, workers, or event-loop pressure are plausible amplifiers
7. Close with evidence. Never claim "safe," "ready," or "understood" without the matching artifact.

## Non-Negotiable Rules
- Keep velocity, but do not let speed skip reasoning.
- Keep outputs portable and avoid host-specific instructions.
- Prefer the lightest viable process for `low` risk and the strongest viable guardrails for `high` or `critical` risk.
- If the task is an incident, prioritize restoration and containment before cleanup or elegance.
- If the failure signature is "app became slow, hot, or unusable," treat it as a performance incident first, not as a cosmetic polish task.
- For render-heavy or browser-heavy incidents, prefer budget-first containment: visibility gating, staged loading, sampling, throttling, and hot-loop inspection before feature expansion.
