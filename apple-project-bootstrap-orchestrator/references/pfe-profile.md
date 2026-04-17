# Project Free Energy Profile

Use the `pfe` profile only when the Apple project is part of the PFE ecosystem.

## Default PFE Behavior

- prefer `adopt_existing` for the main PFEMacOS repo
- install the Apple build harness by default
- install onboarding guidance by default
- write a release profile skeleton by default
- keep local task templates optional

## Consult Chain

When PFE profile is active, consult:
- `$runtime-context-launcher`
- `$model-ux-orchestrator`
- `$qa-automation-engineer`
- `$apple-ecosystem-release-operator`

## PFE Readiness Checks

- real Xcode app-target build path is known
- generator-backed project truth is preserved
- release profile path is present or updated
- companion app identity is separate from sibling Apple app runtime identity

## Guardrails

- do not treat the old desktop scaffold as PFEMacOS source truth
- do not regenerate the main PFEMacOS app in place
- keep PFE-specific wording and defaults out of the base generic flow unless `--profile pfe` is selected
