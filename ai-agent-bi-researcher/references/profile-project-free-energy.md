# Optional Profile: Project Free Energy

Load this file only when ProjectFreeEnergy workspace context is active.

## Profile Objective
Translate generic trend findings into local-first, Apple-silicon-friendly implementation options.

## Adaptation Rules
1. Keep the core report generic; place all profile details in the appendix.
2. Prioritize recommendations that can run locally before cloud-first alternatives.
3. Tie trend actions to existing contracts, model lifecycle, and reliability posture.
4. Keep guidance additive and reversible.

## Output Additions
- `Model and Runtime Fit`: likely impact on model/tool routing.
- `Contract Touchpoints`: contracts and services likely affected.
- `Validation Path`: smoke tests, parity checks, or rollout gates.

## Risk Focus
- Performance or memory regressions on local inference.
- Contract drift between backend and client surfaces.
- Over-broad trend adoption without measurable acceptance criteria.
