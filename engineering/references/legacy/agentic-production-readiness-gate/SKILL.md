---
name: agentic-production-readiness-gate
description: Portable production-readiness gate for agentic engineering. Use when medium-risk or high-risk changes need evidence for coverage, telemetry, rollback, failure semantics, and operational readiness before merge, deploy, or incident closure.
---

# Agentic Production Readiness Gate

Gate risky work on release evidence, not optimism.

Read `references/readiness-checklist.md` for the minimum evidence set and observability expectations.

## Workflow
1. Emit `ReadinessGateV1` with:
   - `coverage`
   - `telemetry`
   - `rollback`
   - `release_risks`
   - `go_no_go`
2. Verify coverage:
   - regression tests or deliberate manual checks for the changed surface
   - critical edge or failure path coverage
   - explicit note when a gap remains
3. Verify telemetry:
   - logs, metrics, traces, or health signals that can prove success and surface failure
   - user-visible failure semantics when the operation degrades
4. Verify rollback and containment:
   - safe disable or revert path
   - blast-radius awareness
   - data integrity considerations during partial failure
5. Issue a clear `go_no_go` outcome with reasons, not vague confidence language.

## Coordination
- Use `$qa-automation-engineer` for regression coverage and repeatable verification.
- Use `$principal_code_auditor_worldclass` for high-risk correctness and reliability review.
- Use `$security-best-practices` or `$security_appsec_worldclass_auditor` when trust boundaries moved.
- Use `$skill-portability-guardian` before shipping new or updated skills broadly.

## Non-Negotiable Rules
- Do not call a change production-ready without evidence.
- Do not treat deployability and debuggability as separate concerns.
- Do not close an incident fix without both recovery evidence and a readiness decision.
