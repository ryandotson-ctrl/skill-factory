# Skill Evolution Regression Gate Contracts v1

## SkillEvolutionRegressionGateResultV1
- `generated_at` (ISO-8601 UTC)
- `status` (`pass` | `warning` | `blocker`)
- `workspace_root` (sanitized path string)
- `changed_skill_ids` (array of strings)
- `checks` (array of `GateCheckV1`)
- `totals` (object)
  - `changed_files`
  - `lines_added`
  - `lines_deleted`
- `recommendation` (string)

## GateCheckV1
- `id` (string)
- `severity` (`info` | `warning` | `blocker`)
- `passed` (boolean)
- `summary` (string)
- `details` (array of strings)

## Status Rule
1. Any failed blocker check => `blocker`.
2. No blocker failures, but failed warning checks => `warning`.
3. Otherwise => `pass`.
