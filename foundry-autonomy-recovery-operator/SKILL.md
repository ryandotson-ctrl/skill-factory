---
name: foundry-autonomy-recovery-operator
description: Portable control-plane recovery operator for autonomous research systems that appear scheduled and healthy but have stopped producing fresh progress. Detects stale inputs, dead single-flight locks, abandoned runs, empty frontier cycles, and next-safe retry actions.
metadata:
  version: 1.0.0
  portability_tier: strict_zero_leak
  scope: global
---

# Foundry Autonomy Recovery Operator

## Use When
- Automations are active but frontier progress is flat.
- Freshness jobs run yet manifests remain stale.
- Accepted runs never reach terminal state.
- Research loops stall behind dead locks, stale worktrees, or runtime crashes.
- The user asks whether autonomy is truly progressing or only appearing alive.

## Prime Directive
Restore truthful autonomous progress without destructive resets.

This skill is for the gap between:
- scheduler health
- runtime health
- freshness health
- frontier health

If the system is "running" but not compounding, this skill must identify the precise choke point and recommend the next safe action.

## Recovery Questions
1. Are the automations active?
2. Are manifests actually fresh or merely present on disk?
3. Are there live runs, dead locks, or abandoned accepted runs?
4. Are frontier cycles producing kept or confirm candidates?
5. Is the runtime degraded, quarantined, or silently wedged?
6. Is the blocker freshness, prep, train, eval, ANE probe, or artifact reconciliation?

## Inputs
- automation definitions and latest run state when available
- frontier artifacts
- runtime health artifacts
- freshness manifests
- run execution artifacts
- stale lock directories and owner PID files
- experiment ledger

## Outputs
- `AutonomyRecoveryAssessmentV1`
- `AutonomyRecoveryActionV1[]`
- `AutonomyRecoveryPlanV1`

## Workflow

### Phase 1: Truth Sweep
Capture:
- latest automation intent
- latest artifact timestamps
- latest frontier timestamps
- latest manifest timestamps
- latest runtime health snapshot

Flag "alive but stalled" when:
- automations are active
- but no recent kept candidates, promotions, or fresh manifests exist

### Phase 2: Stall Classification
Classify the dominant blocker into one or more of:
- `freshness_failed`
- `dead_singleflight_lock`
- `accepted_run_abandoned`
- `prep_budget_exhausted`
- `train_runtime_crash`
- `eval_gate_failure`
- `artifact_contract_drift`
- `ane_lane_poisoning`

### Phase 3: Safe Recovery Gate
Prefer the least-destructive action that restores truthful progress:
- clear dead lock only after PID liveness check fails
- reconcile abandoned runs before retrying
- pause a degraded lane before reopening automations
- require manifest refresh before frontier work
- stop retry storms when the same crash signature repeats

### Phase 4: Retry Plan
Emit a concrete retry sequence with bounded scope:
1. what to repair first
2. what to leave untouched
3. what evidence proves recovery
4. what should pause until the recovery gate passes

## Non-Negotiable Rules
- Never claim autonomy is healthy just because schedules exist.
- Never clear a lock without checking whether its recorded PID is still alive.
- Never reopen a frontier lane until stale accepted runs have terminal state.
- Never recommend broader retries when the failure signature is repeating unchanged.
- Always distinguish `degraded` from `quarantined`.
- Prefer explicit safe retry actions over generic "rerun the workflow".

## Deliverables
1. Recovery assessment
2. Blocker classification
3. Next-safe retry plan
4. Optional implementation steps if the user asks to repair immediately

## Validation
- stale lock is identified as dead only when PID is absent
- stale manifest is identified from timestamp or empty-source evidence
- abandoned accepted run is reconciled to a terminal explanation
- final recommendation names the exact blocker and the exact next retry gate

## References
- `references/contracts-v1.md`
