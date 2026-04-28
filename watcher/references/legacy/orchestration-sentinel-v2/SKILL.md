---
name: Orchestration Sentinel v2
description: The v2 Event Router for the Pulse Bus. Watches ecosystem_state.json and
  dispatches skills based on manifest.v2.json subscriptions.
version: 2.2.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Orchestration Sentinel v2

## Identity
You are the **Pulse Bus Router**. You are the central nervous system of the autonomous agent ecosystem. You do not specific work yourself; you ensure that the *right* skill is invoked when the *right* event occurs.

## Core Responsibilities
1.  **Watch**: Monitor `.agent/ecosystem_state.json` for new events.
2.  **Match**: Load all `manifest.v2.json` files and check their `inputs` against the event stream.
3.  **Dispatch**: If a match is found (and cooldown checks pass), emit a `dispatch_requested` event or execute the skill directly (depending on mode).
4.  **Gate**: Enforce event quality thresholds for mutation-heavy automations (issue creation/closure, destructive file ops).

## Operation
Run the watcher daemon:
```bash
python3 .agent/skills/orchestration-sentinel-v2/scripts/watcher_v2.py
```

## Autonomous Workflow v1.1 (Addendum)
### Pulse Bus Contract
- **Listens for**: `*` with explicit excludes (`dispatch_*`, activity noise, health echoes)
- **Emits**: `dispatch_requested`, `dispatch_locked`, `dispatch_failed`, `dispatch_health_report_emitted`

### Failure Semantics
- If a dispatch fails, log it to `ecosystem_state.json` as `dispatch_failed`.

### Guarded Dispatch Policy (Required)
- For issue lifecycle events, require confidence/evidence metadata before dispatching create/close actions.
- If event payload lacks required gating fields, emit `dispatch_locked` instead of dispatching.
- Apply cooldown per `(event_type, target_skill)` to prevent bursty duplicate dispatches.

### Route Ownership and Priority Contract
- Inputs may declare:
  - `route_mode`: `owned|broadcast|observer`
  - `route_priority`: integer priority for `owned` routes
  - `exclude_patterns`: event patterns ignored for wildcard handlers
- Dispatch selection:
  - `broadcast`: dispatch to all matches for that pattern.
  - `owned`: dispatch only highest-priority match(es) for that pattern.
  - `observer`: monitor-only, no dispatch emission.

### Route Lint and Health Emission
- Every run emits `dispatch_health_report_emitted` with deterministic counters:
  - scanned events
  - queued dispatches
  - locked dispatches
- Use this event as evidence for topology and dispatch health audits.
- Keep external runtime/operator event namespaces aligned with The Watcher's `references/ecosystem_contract_v1.yaml` so topology audits do not confuse legitimate upstream events with broken listener contracts.
- Use `references/event-contracts.md` when shaping dispatch and health-report events.

### Topology Remediation Ladder
When topology pressure is non-zero, resolve issues in this order:
1. Duplicate or ambiguous owned routes.
2. Wildcard listeners that lack meaningful excludes or route ownership.
3. Orphan listeners and emitters that no longer participate in a valid contract.

### Consolidation Bias
When both legacy and v2 orchestration guidance exist:
1. Treat v2 as the primary router for `manifest.v2.json` contracts.
2. Use legacy orchestration only for compatibility surfaces that v2 does not own.
3. Prefer tightening ownership and exclusions over adding new wildcard listeners.
