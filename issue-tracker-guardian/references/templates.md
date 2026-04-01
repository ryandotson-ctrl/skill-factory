# Issue Templates

## Bug Template
Title:
`[Bug] <short symptom>`

Body:
```md
## Summary
<what happened>

## Expected
<expected behavior>

## Actual
<actual behavior>

## Reproduction
1. ...
2. ...
3. ...

## Evidence
- <log, stack, trace, screenshot link>

## Classification
- Type: bug
- Severity: <critical|high|medium|low>
- Component: <component>

<!-- issue_guardian:fingerprint=<sha1> -->
<!-- issue_guardian:type=bug -->
<!-- issue_guardian:severity=<level> -->
<!-- issue_guardian:component=<component> -->
```

## Enhancement Template
Title:
`[Enhancement] <capability request>`

Body:
```md
## Problem
<current pain>

## Proposed Change
<feature proposal>

## Acceptance Criteria
- [ ] ...
- [ ] ...

## Evidence / Context
- <user reports, links, notes>

## Classification
- Type: enhancement
- Severity: <critical|high|medium|low>
- Component: <component>

<!-- issue_guardian:fingerprint=<sha1> -->
<!-- issue_guardian:type=enhancement -->
<!-- issue_guardian:severity=<level> -->
<!-- issue_guardian:component=<component> -->
```

## Lifecycle Update Comment Template
```md
Issue Guardian Update
- Action: <opened|updated|duplicate|reopened|closure_candidate|blocked|closed>
- Confidence: <0.00-1.00>
- Fingerprint: `<sha1>`
- Evidence added:
  - <item>
- Verification:
  - <check name>: <pass|fail|skipped>
- Reason: <short reason>
```
