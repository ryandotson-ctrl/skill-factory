---
name: conversation-skill-evolution-director
description: Session-aware meta-skill that serves as The Watcher's core session-to-action engine and as a standalone strategist, deciding whether to update existing skills or create new ones with additive, portability-safe evolution actions.
metadata:
  version: 1.2.0
  scope: global
  portability_tier: strict_zero_leak
  requires_env: []
  project_profiles: []
---

# Conversation Skill Evolution Director

## Overview

Use this when the user asks:
- "Based on everything in this conversation/project, what skills should we update?"
- "Do we need a new skill or can we extend existing ones?"
- "Create a meta-skill that decides update vs new across any project."

This skill converts session evidence into deterministic, additive skill-evolution actions.
It also serves as The Watcher's always-on session-to-action engine, so its contracts
must remain stable for both embedded and standalone use.

## Non-Negotiable Rules

1. Additive only: recommend `add/extend/augment`; never destructive replacement.
2. Portability first: avoid host-specific assumptions and absolute path leakage in outputs.
3. Evidence-linked decisions: every recommendation must cite concrete run/context evidence.
4. No forced novelty: default to updating existing skills when overlap is strong.
5. Confidence honesty: low-confidence recommendations must be suppressed, not promoted.
6. Preserve per-skill intelligence: every recommendation must keep the target skill's identity, portability posture, and pulse participation legible.
7. Wisdom is monotonic: recommendations may append, strengthen, and clarify, but never silently discard prior skill intelligence.

## Workflow

### Phase 1: End-to-End Context Sweep

1. Capture current objective, constraints, and acceptance gates from the active workspace.
2. Extract session outcomes:
   - wins
   - failures
   - regressions
   - recovered blockers
3. Build an evidence list from available artifacts (run decisions, ledgers, reports, task boards).
4. Snapshot relevant current skills (name, purpose, overlap signals).

### Phase 2: Capability Gap Map

Classify gaps into reusable capability buckets:
- entitlement/governance
- launch/budget control
- compatibility/transform
- eval/quality assurance
- telemetry/semantics
- domain-specialized execution

For each gap, record:
- observed pain point
- frequency
- operational impact
- existing skill overlap candidates

### Phase 3: Update-vs-New Decision Gate

Use the matrix in `references/contracts-v1.md`:
- Choose `update_existing` when overlap is high and intent is adjacent.
- Choose `create_new` only when overlap is low and demand repeats.
- Choose `defer` when confidence is low or evidence is weak.

### Phase 4: Recommendation Package

Emit:
1. `SkillEvolutionAssessmentV1` (summary + confidence + suppressed ideas)
2. `SkillActionV1[]` (update/new/defer actions with rationale)
3. `SkillExecutionPlanV1` (ordered implementation steps + validation gates)
4. `SkillContinuityProofV1` for every non-deferred action

Each action must include:
- additive change scope
- portability/privacy note
- compatibility risk
- rollback hint
- preservation proof for pulse participation, portability, and append-only wisdom growth

### Phase 5: Optional Execution Path

If the user asks to implement:
1. Create or patch skill files in canonical root.
2. Keep edits additive and non-destructive.
3. Validate structure and frontmatter.
4. Report exact changed files and why.

## Output Expectations

Default response format:
1. Recommended actions by priority (`update`, `new`, `defer`)
2. Why each action is justified
3. What to implement now vs later
4. Explicit "no new skill needed" outcome when applicable

When embedded inside The Watcher:
- keep the same underlying contracts
- provide compact action summaries for chat
- preserve the full `SkillEvolutionAssessmentV1`, `SkillActionV1[]`, and `SkillExecutionPlanV1` in JSON state
- inherit and preserve `IndividualSkillIntelligenceV1` instead of replacing per-skill context with generic ecosystem advice

## Pairing Guidance

Use with:
- `The Watcher` (`$skill_director`) as the primary host for always-on ecosystem runs and root governance
- `proactive-skill-evolution-planner` for recurring capability-gap planning
- `skill-portability-guardian` for portability-safe hardening
- `research-director` when updates depend on fast-changing external platforms
