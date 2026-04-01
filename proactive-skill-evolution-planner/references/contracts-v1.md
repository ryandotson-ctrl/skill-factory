# Proactive Skill Evolution Contracts v1

This reference defines deterministic output contracts for proactive evolution runs.

## SkillEvolutionAssessmentV1
- `generated_at` (ISO-8601)
- `confidence` (0-1)
- `workspace_goal_summary` (string)
- `coverage_summary` (object)
- `suppressed_ideas` (array of objects)

## SkillActionV1
- `action_type` (`update_existing` | `create_new` | `defer`)
- `target_skill_id` (string, required for updates)
- `proposed_skill_id` (string, required for new skill actions)
- `confidence` (0-1)
- `reason` (string)
- `evidence_refs` (array of sanitized refs)
- `additive_scope` (string)
- `portability_note` (string)
- `suppression_reason` (string, required when `action_type=defer`)
- `normalized_signal_tags` (array of strings, optional)
- `repeat_evidence_count` (integer, optional)

## SkillExecutionPlanV1
- `generated_at` (ISO-8601)
- `ordered_steps` (array of strings)
- `validation_gates` (array of strings)
- `rollback_hints` (array of strings)
- `assumptions` (array of strings)

## Deterministic Scoring Inputs
- `overlap_score` (1-5)
- `demand_score` (1-5)
- `impact_score` (1-5)
- `reuse_fit_score` (1-5)
- `confidence_score` (1-5)
- `signal_tags` (array of strings, optional)
- `repeat_evidence_count` (integer, optional)

## Scoring Output
- `total_score` (0-100)
- `recommended_action` (`update_existing` | `create_new` | `defer`)
- `score_breakdown` (object)
- `normalized_signal_tags` (array of strings when signal-aware scoring is used)
