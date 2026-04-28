---
name: proactive-skill-evolution-planner
description: Continuously detects capability gaps from workspace goals and recent activity, then proposes additive, portability-safe upgrades and new skills.
version: 1.4.0
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Proactive Skill Evolution Planner

## Purpose
Plan skill evolution before bottlenecks appear by turning workspace intent and execution telemetry into clear upgrade actions.

## Workflow
1. Ingest workspace goal intelligence and current skill inventory.
2. Ingest recent high-signal execution evidence such as parity claims, source-truth requirements, manual audit needs, and performance incidents.
3. Score skill coverage against active workspace demands.
4. Identify:
   - update candidates (existing skills to extend)
   - net-new skill opportunities
5. Produce an evolution plan with:
   - confidence score
   - evidence refs
   - additive implementation direction
   - portability/privacy guardrails

## Planning Rules
1. Prefer updating an existing skill when coverage is adjacent.
2. Propose a new skill only when overlap is low and repeated demand is strong.
3. Include suppression reasons for low-confidence ideas.
4. Keep recommendations deterministic and reproducible.
5. Emit machine-readable artifacts for ranking and review.
6. Treat single-workspace, single-session incidents as upgrade signals first when existing skill overlap is plausible.

## Reference Parity and Incident Signal Intake (v1.4)
Use these signals as first-class planning evidence when they appear in workspace activity, postmortems, or explicit candidate input:
- `reference_parity`
- `source_truth`
- `manual_audit`
- `performance_incident`
- `render_pressure`
- `public_first_data`

Planning behavior:
1. When these signals appear and overlap with existing QA, orchestration, governance, or audit skills is adjacent, prefer `update_existing`.
2. Do not recommend `create_new` for a single strong incident unless repeated evidence exists across sessions, workspaces, or explicit candidate inputs.
3. If the strongest evidence is a regression caused by recent hardening or polish work, prioritize upgrades that improve prevention and routing before proposing a new domain specialist.
4. Keep signal names sanitized and portable in every emitted artifact.

## Additive and Portability Contract
1. All recommended changes must be additive and non-destructive.
2. Never prescribe deletion/removal of existing skill logic.
3. Require portability-safe notes on every recommendation.
4. Use sanitized, machine-agnostic evidence references.

## Canonical Root and Mirror Scope
For mirrored governance skills:

1. Treat codex as the canonical authoring root unless the user explicitly overrides it.
2. Treat antigravity as a distribution mirror when contracts are semantically equivalent.
3. Recommend `mirror`, `hold`, or `manual review` explicitly when mirrored copies drift.

## Intervention-First Planning Contract
When ecosystem posture is `intervene`, rank evolution work in this order:

1. Control-plane and topology health fixes.
2. Governance and mirror-closure work for inventory, portability, and evolution skills.
3. Domain specialist upgrades tied to current workspace intent.

Do not let lower-leverage domain upgrades outrank unresolved control-plane or mirrored-governance drift without explicit contrary evidence.

## Scoring Contract (v1.1)
Use deterministic scoring to avoid subjective drift.

1. Normalize each candidate with:
   - `overlap_score` (1-5)
   - `demand_score` (1-5)
   - `impact_score` (1-5)
   - `reuse_fit_score` (1-5)
   - `confidence_score` (1-5)
2. Decision preference:
   - high overlap + high reuse -> `update_existing`
   - low overlap + high repeated demand -> `create_new`
   - low confidence -> `defer`
3. Produce artifacts defined in `references/contracts-v1.md`.
4. Use `scripts/score_evolution_plan.py` when deterministic ranking is required.

## Git Signal Intake (v1.2)
Reduce manual prep by deriving candidates from active skill edits.

1. Use `--auto-from-git` to infer update candidates from changed skill paths.
2. Scope inference with `--workspace-root` (defaults to current working directory).
3. Optional manual + inferred merge:
   - pass `--input` and `--auto-from-git` together to merge both sources.
4. Deterministic merge rule:
   - dedupe by target/proposed skill key
   - keep strongest confidence/impact signal when duplicates overlap

## Repetition Gate for Net-New Skills (v1.4)
Before recommending `create_new`, require at least one of:
1. repeated low-overlap demand across multiple candidate inputs,
2. explicit repeat evidence count from workspace/session telemetry,
3. cross-workspace or cross-session recurrence from watcher-grade intelligence.

If repeated evidence is absent, bias toward `update_existing` when overlap is adjacent or `defer` when confidence is weak.

## Output Artifacts (v1.2)
1. `SkillEvolutionAssessmentV1`
2. `SkillActionV1[]`
3. `SkillExecutionPlanV1`

Each action must include:
- confidence
- evidence refs
- additive scope
- portability note
- suppression reason when deferred
- normalized signal tags when signal-aware scoring was used

## Coordination Addendum
When the user explicitly requests an end-to-end, conversation-grounded decision on
"update existing skills vs create a new skill," hand off to or pair with
`conversation-skill-evolution-director` for session-level synthesis.

When watcher posture, workspace evidence, and conversation evidence disagree:
1. prefer existing-skill upgrades first,
2. suppress net-new skills until repetition is explicit,
3. record the suppressed idea with the missing repetition evidence.
