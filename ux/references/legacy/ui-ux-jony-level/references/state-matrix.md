# State Matrix

Every meaningful surface should specify these states unless they are truly inapplicable.

## Required States
- default
- hover or focus-visible where relevant
- active or pressed
- loading
- success
- empty
- error
- offline or degraded network
- permission denied or blocked

## Input States
- untouched
- focused
- valid
- invalid
- recovering after error
- disabled

## Edge Cases
- long names or labels
- zero data
- extremely large data sets
- partial failure
- stale data
- slow network
- interrupted action
- undoable destructive flow

## Failure Semantics
- distinguish request accepted from operation complete
- never imply success before verification
- pair every error with next-step recovery guidance when possible
