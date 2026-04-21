# Evidence Contracts

Use these contracts to turn research into decision-ready output.

## EvidenceRowV1
- `claim`
- `source`
- `source_type`
- `published_at`
- `version_or_tag`
- `confidence`
- `notes`

## DecisionBriefV1
- `decision_target`
- `constraints`
- `facts`
- `inferences`
- `conflicts`
- `recommended_action`
- `fallback_or_experiment`

## Conflict Resolution Ladder
1. official vendor docs or release notes
2. maintainer repository or package registry
3. local smoke test when feasible
4. bounded uncertainty note if conflict remains
