# Contracts V1

## Decision Matrix

Use the following deterministic rubric:

- `update_existing`:
  - overlap_with_existing_skill >= 2 (0-3 scale)
  - demand_frequency >= 2 occurrences
  - no semantic-intent conflict
  - launched-artifact or user-visible evidence may raise confidence when source-only evidence was ambiguous
- `create_new`:
  - overlap_with_existing_skill <= 1
  - demand_frequency >= 2 occurrences
  - impact >= medium
  - do not use when the failure is a prompt/topic variant of an existing answer-quality, UX, eval, or grounding problem
- `defer`:
  - confidence < 0.6
  - evidence insufficient or conflicting

## SkillEvolutionAssessmentV1

```json
{
  "schema": "SkillEvolutionAssessmentV1",
  "generated_at": "ISO-8601",
  "workspace_scope": "string",
  "objective_summary": "string",
  "evidence_refs": ["string"],
  "recommendation_confidence": 0.0,
  "evidence_precedence": ["string"],
  "suppressed_ideas": [
    {
      "idea": "string",
      "reason": "string"
    }
  ]
}
```

## SkillActionV1

```json
{
  "action": "update_existing|create_new|defer",
  "target_skill": "string",
  "priority": "P0|P1|P2",
  "rationale": "string",
  "evidence_refs": ["string"],
  "additive_scope": "string",
  "portability_note": "string",
  "risk": "low|medium|high",
  "confidence": 0.0,
  "evidence_precedence_note": "string"
}
```

## SkillExecutionPlanV1

```json
{
  "schema": "SkillExecutionPlanV1",
  "steps": [
    {
      "order": 1,
      "action_id": "string",
      "implementation_note": "string",
      "validation_gate": "string"
    }
  ],
  "rollback_note": "string"
}
```
