---
name: cross-workspace-goal-intelligence
description: Builds a unified, privacy-safe goal and momentum map across active workspaces, then emits actionable intelligence for skill routing and proactive updates.
version: 1.0.1
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Cross Workspace Goal Intelligence

## Purpose
Maintain a live, additive understanding of:
- each workspace goal
- each workspace momentum and recent activity
- cross-workspace conflicts, overlap, and priority pressure

Then emit deterministic intelligence that other skills can consume.

## Workflow
1. Discover active workspaces from The Watcher (`$skill_director`) context.
2. Ingest goal signals from explicit context files, README/roadmap text, and recent git activity.
3. Normalize and sanitize all signals for portability and privacy safety.
4. Build a workspace goal graph:
   - goal summary per workspace
   - confidence score
   - recent momentum score
   - cross-workspace overlap/gap indicators
5. Emit a compact intelligence payload with suggested priorities.

## Output Contract
Always provide:
- `workspace_profiles`: per-workspace goal + momentum
- `cross_workspace_alignment`: overlap/conflict map
- `priority_queue`: ordered workspace focus list
- `recommended_skill_targets`: skills likely needing proactive evolution

## Additive and Portability Contract
1. Recommendations must be additive and non-destructive.
2. Never suggest replacing or removing existing skill intent.
3. Keep outputs path-agnostic and sanitized.
4. Prefer stable, machine-independent references.

## Workspace Goal Alignment (SideQuests Signal)
When the current workspace profile indicates SideQuests-style momentum, prioritize:
1. Runtime reliability and truthfulness hardening before capability expansion.
2. Action-path correctness over passive telemetry summaries.
3. Short-cycle validation loops tied to recent user-reported regressions.

This section is guidance-oriented and must remain portable:
- do not hardcode local absolute paths
- do not embed user-identifying literals
- do not convert this profile into a destructive migration rule

## Trigger Examples (Intelligence + Momentum)
Treat phrases like these as strong signals to activate cross-workspace goal synthesis:
1. "run latest skill director and apply recommendations"
2. "what changed recently and what should we update next"
3. "use momentum and intelligence from this workspace to prioritize skills"
4. "non-destructive update based on current activity"

## Proactive Near-Term Guidance
After building workspace profiles, proactively suggest near-term, additive updates when both conditions hold:
1. The workspace is active within the recent window.
2. Evidence references show clear goal/momentum overlap with existing skills.

Guidance rules:
1. Propose a minimal update set first (highest confidence only).
2. Include explicit evidence refs for each suggestion.
3. Defer low-confidence ideas into suppressed recommendations instead of auto-promoting.
4. Preserve portability/privacy constraints in every proposal.

## Event Contract (Recommended)
Inputs:
- `skill_director_context_ingest_requested`
- `stability_gate_check`

Outputs:
- `workspace_goal_intelligence_emitted`
- `skill_recommendation_emitted`
