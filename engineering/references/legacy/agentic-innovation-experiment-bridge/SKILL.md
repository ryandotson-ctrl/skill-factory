---
name: agentic-innovation-experiment-bridge
description: Portable experiment-planning bridge that turns ambitious agentic ideas into bounded, evidence-driven experiments. Use when a user wants innovation without losing rigor and Codex must define a hypothesis, blast radius, eval plan, and promotion criteria before implementation.
---

# Agentic Innovation Experiment Bridge

Turn bold ideas into disciplined experiments instead of vague ambition.

Read `references/experiment-bridge-template.md` for the experiment brief and promotion rules.

## Workflow
1. Emit `ExperimentBridgeV1` with:
   - `hypothesis`
   - `blast_radius`
   - `eval_plan`
   - `promotion_criteria`
2. Bound the idea:
   - define the smallest meaningful slice
   - limit operational and user-facing blast radius
   - state what failure looks like
3. Route to `$skunkworks-innovation-strategist` for the strongest technical direction and implementation options.
4. Route to `$eval-flywheel-orchestrator` for repeatable scoring, regression protection, and promotion evidence.
5. If the experiment is promoted toward real delivery, hand off to:
   - `$agentic-design-contract-architect`
   - `$agentic-performance-reality-guardian`
   - `$agentic-production-readiness-gate`

## Non-Negotiable Rules
- Do not ship "innovation" without a bounded hypothesis.
- Do not confuse novelty with value.
- Do not promote an experiment without explicit evaluation evidence.
