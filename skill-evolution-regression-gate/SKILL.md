---
name: skill-evolution-regression-gate
description: Deterministic pre-commit policy gate for skill evolution changes. Enforces additive bias, portability safety, and manifest parity before skill updates are accepted.
version: 1.1.0
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Skill Evolution Regression Gate

## Purpose
Provide one deterministic go/no-go gate for skill-library changes before merge or release.

## Use When
- You changed one or more skills and want a policy check before commit.
- You need additive-only and portability-safe guarantees for skill updates.
- You want manifest parity verification in the same gate output.
- A skill evolution plan has already been emitted and needs validation before execution or merge.

## Checks (v1)
1. Skill change scope detection.
2. Portability leak scan (`/Users/<you>/...`, `/home/<you>/...`, `C:\Users\<you>\...` patterns).
3. Manifest parity (`manifest.json` and `manifest.v2.json` coherence).
4. Manifest JSON validity.
5. Additive-bias signal from `git diff --numstat` (warn when deletions dominate).

## Output
`SkillEvolutionRegressionGateResultV1` with:
- `status` (`pass`, `warning`, `blocker`)
- `checks[]` (id, severity, passed, summary, details)
- `changed_skill_ids[]`
- `totals` (files and line delta)
- `recommendation`

## Non-Negotiable Rules
1. Block when portability leaks are detected.
2. Block when required manifest parity or JSON validity fails.
3. Keep output deterministic and path-safe.
4. Report warnings separately from blockers.

## Routing Ownership
1. `skill_evolution_requested` belongs to `proactive-skill-evolution-planner` as the first responder.
2. This gate should validate `skill_evolution_plan_emitted` and direct skill-file changes, not compete as a co-equal planner trigger.
3. If both planning and gate validation are needed, the expected order is planner first, gate second.

## References
- `references/contracts-v1.md`
- `scripts/run_gate.py`
