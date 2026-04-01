---
name: agentic-incident-triage-commander
description: Portable production incident triage commander for agentic systems. Use when something is down, degraded, flaky, timing out, corrupting data, or failing under pressure and Codex must reconstruct runtime mental models, request evidence, choose the safest mitigation, and drive recovery.
---

# Agentic Incident Triage Commander

Treat the 3 a.m. page as a reasoning problem, not a prompting contest.

Read `references/incident-playbook.md` for the response sequence and common failure signatures.

## Workflow
1. Emit `IncidentTriageV1` with:
   - `symptom`
   - `likely_causes`
   - `evidence_needed`
   - `safe_mitigation`
   - `next_fix`
2. Stabilize first:
   - reduce blast radius
   - preserve data integrity
   - choose the safest mitigation that can restore service quickly
3. Reconstruct the runtime mental model:
   - what changed
   - where requests or events flow
   - what shared resources are saturated or failing
4. Request evidence in a useful order:
   - current symptom and scope
   - recent change or deploy signals
   - logs, metrics, traces, queue depth, or database pressure
   - recovery confirmation after mitigation
5. Route to specialists when the signature is clear:
   - `$thread-safety-auditor` for races or shared-state corruption
   - `$async-hygiene-monitor` for stalls, blocking, or concurrency collapse
   - `$agentic-performance-reality-guardian` for overload or amplification failures
6. After stabilization, hand off the durable repair to `$agentic-design-contract-architect` and `$agentic-production-readiness-gate`.

## Non-Negotiable Rules
- Restore service safely before optimizing elegance.
- Do not thrash between guesses without collecting the next decisive piece of evidence.
- Do not declare recovery until the symptom is gone and the key signal confirms it.
