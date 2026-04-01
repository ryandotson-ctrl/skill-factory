---
name: agentic-design-contract-architect
description: Portable design-contract builder for agentic engineering. Use when a task needs an explicit approach, interfaces, invariants, failure modes, and acceptance checks before implementation, especially for medium-risk or high-risk features, refactors, integrations, and critical paths.
---

# Agentic Design Contract Architect

Turn ambiguous work into an explicit contract before code is written.

Read `references/design-contract-template.md` when scoping a contract or enumerating failure modes.

## Workflow
1. Emit `DesignContractV1` with:
   - `approach`
   - `interfaces`
   - `invariants`
   - `failure_modes`
   - `acceptance_checks`
2. Define interfaces explicitly:
   - inputs and outputs
   - API or event boundaries
   - storage, cache, queue, and config touchpoints
   - concurrency or lifecycle assumptions
3. Define invariants that must remain true even under retry, partial failure, bad input, or rollback.
4. Enumerate concrete failure modes. Include correctness, performance, security, and operability when relevant.
5. Define acceptance checks that another engineer or agent can run without inventing missing policy.
6. Keep the contract proportional. Small changes need a small contract, but never skip hidden complexity.

## Coordination
- Escalate to `$agentic-performance-reality-guardian` when work amplification, throughput, polling, batching, cache, or query shape matters.
- Escalate to `$security-best-practices` or `$security_appsec_worldclass_auditor` when trust boundaries, auth, secrets, or untrusted input are involved.
- Hand off to `$qa-automation-engineer` once acceptance checks are clear.

## Non-Negotiable Rules
- Do not confuse "working in local tests" with "safe by design."
- Do not leave interfaces or invariants implied.
- If you cannot explain the contract, route to `$agentic-understanding-receipt-enforcer` before proceeding.
