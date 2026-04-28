# Report Template

Use this template to keep output deterministic and decision-ready.

## Required Markdown Sections
1. `## Executive Summary`
2. `## Top Trends With Evidence Grade`
3. `## Decision Lanes`
4. `## Companion Skill Fit`
5. `## Decision Matrix`
6. `## 30/60/90-Day Action Backlog`
7. `## Risks and Unknowns`
8. `## Optional Project Profile Appendix` (only when a profile is active)

## Required Trend Fields
- `name`
- `summary`
- `evidence_grade` (A/B/C/D)
- `claim_label` (`[FACT]`, `[INFERENCE]`, `[ASSUMPTION]`)
- `score` (0-100)
- `sources` (list of URL + date)

## Required Decision Matrix Fields
- `action`
- `expected_impact` (1-5)
- `feasibility` (1-5)
- `evidence_strength` (1-5)
- `effort` (1-5, lower is easier)
- `time_to_value` (1-5, lower is faster)
- `owner`
- `confidence_note`

## Required Decision Lanes
- `adopt_now`
- `prototype_next`
- `monitor`

## Companion Skill Fit Fields
- `skill`
- `fit`
- `why`

## 30/60/90 Expectations
- `30 Days`: low-risk pilots and instrumentation improvements.
- `60 Days`: production hardening and integration expansion.
- `90 Days`: scale decisions and deprecation/pivot recommendations.

## Output Footer
Always append:
- `Generated At`: absolute timestamp
- `Evidence Window`: oldest and newest source dates used
- `Assumptions`: explicit list, or `None`
