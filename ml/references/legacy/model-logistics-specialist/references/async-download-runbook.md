# Async Download Runbook

Use this runbook when model acquisition blocks request/response behavior.

## Goals
- Keep API responsive while model download runs.
- Provide truthful, monotonic progress signals.
- Validate model before marking runnable.

## Preferred Architecture
1. `POST /model/download` starts async job and returns `job_id`.
2. Worker handles download and validation off request thread.
3. `GET /model/download/{job_id}` returns state and progress.
4. Completion path updates catalog and emits runnable state only after verification.

## Required States
- `queued`
- `downloading`
- `validating`
- `completed`
- `failed`
- `canceled`

## Failure Semantics
- Failure must include user-safe reason and recovery hint.
- Failed job must not replace active model selection automatically.
- Partial artifacts must be marked non-runnable until verified.

## Verification Checklist
1. Trigger request returns in under 500ms under expected load.
2. Progress updates at deterministic intervals.
3. Concurrent chat requests continue to stream responses.
4. Worker crash does not corrupt active runtime state.
