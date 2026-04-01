# Incident Playbook

## Response Order
1. Confirm the symptom and blast radius.
2. Protect users and data.
3. Collect the next decisive piece of evidence.
4. Choose the safest mitigation.
5. Verify recovery with a real signal.
6. Capture the durable fix and readiness follow-up.

## Common Failure Signatures
- Saturation
  - clues: CPU, memory, queue depth, connection pool exhaustion, timeouts
- Amplification
  - clues: one action generating many requests, retries, or jobs
- Concurrency bug
  - clues: flakiness, races, duplicate work, inconsistent state
- Dependency failure
  - clues: sudden latency increase, upstream errors, stale or partial data
- Bad release
  - clues: sharp regression after deploy, canary, or config flip

## Evidence Order
- Symptom and timestamp
- Scope and impacted path
- Recent deploy or config changes
- Runtime signals
- Recovery proof

## Mitigation Bias
- Prefer reversible mitigation over risky live surgery.
- Prefer containment over broad rewrites during the incident.
- Prefer one well-supported hypothesis over many weak guesses.
