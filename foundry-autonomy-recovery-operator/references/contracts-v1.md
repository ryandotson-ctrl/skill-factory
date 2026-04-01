# Contracts V1

## AutonomyRecoveryAssessmentV1

```json
{
  "schema": "AutonomyRecoveryAssessmentV1",
  "generated_at": "ISO-8601",
  "autonomy_state": "healthy|alive_but_stalled|blocked|degraded",
  "dominant_blockers": ["string"],
  "evidence_refs": ["string"],
  "confidence": 0.0
}
```

## AutonomyRecoveryActionV1

```json
{
  "action_id": "string",
  "category": "freshness|runtime|artifact|lock|frontier|automation",
  "severity": "P0|P1|P2",
  "recommended_action": "string",
  "evidence_refs": ["string"],
  "safety_gate": "string"
}
```

## AutonomyRecoveryPlanV1

```json
{
  "schema": "AutonomyRecoveryPlanV1",
  "steps": [
    {
      "order": 1,
      "goal": "string",
      "action_id": "string",
      "validation_gate": "string"
    }
  ],
  "stop_conditions": ["string"]
}
```
