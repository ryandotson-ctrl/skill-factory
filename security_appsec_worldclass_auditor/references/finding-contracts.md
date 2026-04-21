# Finding Contracts

Use these contracts to keep security reviews actionable and evidence-backed.

## SecurityFindingV1
- `title`
- `severity`
- `affected_surface`
- `attack_path`
- `evidence`
- `business_impact`
- `recommended_fix`
- `verification_plan`

## Severity Guidance
- `critical`: direct compromise, secret exposure, or trust-boundary failure
- `high`: exploitable authorization, injection, or sensitive-data weakness
- `medium`: real weakness with limited preconditions or constrained blast radius
- `low`: hygiene issue, defense-in-depth gap, or hardening opportunity

## Review Output Rules
- Put findings first.
- Separate confirmed findings from open questions.
- Prefer fixes engineers can ship over abstract advice.
