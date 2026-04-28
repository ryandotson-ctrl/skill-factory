# Design Contract Template

## Template
```text
DesignContractV1
- approach:
- interfaces:
  - inputs:
  - outputs:
  - APIs/events:
  - storage/cache/queue/config:
  - concurrency/lifecycle assumptions:
- invariants:
- failure_modes:
- acceptance_checks:
```

## Failure-Mode Prompts
- What breaks if this work runs twice?
- What breaks if it runs slowly?
- What breaks if dependencies return partial or stale data?
- What breaks if the shape of input changes?
- What breaks if rollback happens halfway through?
- What breaks at 10x the expected usage?

## Interface Checklist
- Name the producer and consumer at every boundary.
- Name the state that must remain consistent.
- Name the timeout, retry, or ordering assumptions if they matter.
- Name the exact acceptance check that proves the contract held.
