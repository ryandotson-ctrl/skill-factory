---
name: autonomous-stream-validator
description: Validates SSE stream integrity and run-ledger consistency for PFEMacOSApp
  backend responses.
version: 2.7.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Autonomous Stream Validator

## Identity
You verify that backend streaming is functionally correct, not just connected.

## Current Stream Contract
- Status events: `status`
- Answering events: `answer`
- Error events: `error` and `run.error`
- Run timeline events: `run.started`, `run.step.started`, `run.tool.call`, `run.tool.result`, `run.step.finished`, `run.finished`
- Terminal truth surfaces: visible assistant answer, typed terminal error, and runtime/timeline signals

## Trigger
- "Stream is stuck"
- "It says generating forever"
- "Timeline is wrong"
- "Answer got cut off"
- "Worker Error: Conversation roles must alternate..."
- "It keeps repeating itself"
- "It leaked chain-of-thought"
- "It spammed `Assistant:` / `User:` in the answer"

## Workflow
1. Capture event sequence for a single request.
2. Validate ordering and completeness:
   - `run.started` exists before run step events.
   - Step indices progress correctly.
   - Every started step reaches `run.step.finished`.
   - Run ends with `run.finished` or `run.error`.
3. Validate answer channel:
   - First-token latency is reasonable.
   - No long silent gaps without terminal event.
   - No runaway repetition loops, role-prefix echo, or semantic no-progress streams.
   - Hidden reasoning and planning text do not reach the visible answer lane.
   - Reasoning progress without a visible final answer must not persist indefinitely; the stream must finalize or fail explicitly.
4. Validate persistence parity:
   - Streamed run/tool events match DB ledger entries.
5. Emit a pass/fail report with exact breakpoints.

## Generation Pathology Validation (NEW v2.2)
Goal:
- Detect streams that are technically alive but functionally broken.

Validation:
- Role-prefix contamination:
  - `Assistant:`, `User:`, `System:`, or similar template scaffolding must not repeat in the visible answer stream.
- Repetition pathology:
  - repeated identical lines
  - repeated short n-grams with low novelty growth
  - repeated continuation cycles that do not add useful content
- Reasoning leakage:
  - `<think>`/`<analysis>` style content or planning narration must not appear in the user-visible answer lane.
- Degradation semantics:
  - once a pathology threshold is crossed, the stream should terminate or degrade with an explicit typed failure/degraded state instead of continuing to spray junk into the UI.

Definition of Done:
- A pathological generation can be detected from the event stream and is prevented from presenting as a healthy completed answer.

## Critical Failure Class: Role Alternation Crash
Symptom:
- `Worker Error: Conversation roles must alternate user/assistant/user/assistant/...`

Meaning:
- The model worker rejected the prompt format (usually strict `apply_chat_template` enforcement).

Root Causes (common):
- Concurrent in-flight requests for the same session cause the backend to send `user,user` (assistant reply not persisted yet).
- A prior failure path persisted the user message but never persisted an assistant message, corrupting alternation.

Required Validation:
- Per-session serialization exists for `/mlx/chat` so one request per `session_id` is in-flight at a time.
- Worker-side history normalization exists so even if `user,user` arrives, it is merged into a single user turn.

Definition of Done:
- This error cannot be reproduced by sending two prompts rapidly in the same session.

## Timeline Truthfulness (No False “Completed”)
Hard rule:
- A run may be marked `completed` only when generation succeeded.

Validation:
- If any `error` event occurs, run must end with `run.error` (not `run.finished`).
- `run.step.finished` for “Generate answer” must be `failed` when generation failed.

## Terminal Surface Parity (NEW v2.6)
Hard rule:
- If the stream reaches a failed terminal state with no visible final answer, the user-facing assistant message must surface a typed failure message, not only the timeline/runtime panel.

Validation:
- Treat these as distinct but required-to-agree surfaces:
  - timeline truth (`run.error`, failed steps, tool/result status)
  - runtime truth panel (`generation guard`, degradation, route/model messages)
  - visible assistant terminal surface (`Error: ...` or equivalent when no answer exists)
- If `run.error` or failed `turn.completed` carries an error payload and no visible answer is present, the assistant terminal surface must render that failure.
- Reject flows where timeline shows failure but the assistant bubble stays blank.
- Reject flows where a recoverable terminal error overwrites a real visible answer; visible-answer truth outranks recoverable error text.

Regression expectations:
- `run.error` with explicit `error` field reaches the terminal assistant message when no answer exists
- failed `turn.completed` with only `content` still reaches the terminal assistant message when no answer exists
- a successful visible answer suppresses later recoverable terminal copy instead of being replaced by it

## Pre-Stream Responsiveness Invariant (NEW v2.7)
Hard rule:
- The user-facing transcript must show immediate local progress before backend readiness or model probes complete.

Validation:
- Treat send responsiveness as a required part of stream truth, not a separate cosmetic concern.
- On `Send` or `Return`, validate that:
  - the user message appears immediately
  - an assistant placeholder appears immediately
  - a local progress status such as `Working...` or `Reading your document...` appears before delayed probe completion
- Reject flows where stream startup is technically correct but the UI remains visually inert while preflight work happens offscreen.

Regression expectations:
- delayed chat-route readiness still yields an immediate assistant placeholder
- delayed model probing still yields an immediate local progress status
- attachment sends use attachment-aware local progress copy before the first SSE event arrives

## Terminality Invariant (NEW v2.3)
Hard rule:
- A request may not stop at `reasoning.summary`, `working`, or other progress-only states without either:
  - a visible final-answer lane result, or
  - a typed terminal failure/degraded event.

Validation:
- If reasoning summary or progress events exist and no final answer follows within the bounded terminal window, mark the stream invalid.
- Stability or repair passes that produce no visible answer must transition into finalizer rescue or an explicit typed terminal failure, never silent completion or permanent spinner state.

## Finalizer Availability Invariant (NEW v2.4)
Hard rule:
- If stream phases show `task_model` and/or `repair`, and a safe finalizer is available after any mid-turn downgrade, the stream must attempt that finalizer lane before emitting a stale pathology terminal state.

Validation:
- Treat a stale pathology error as invalid when the model was downgraded into a safe finalizer-backed lane during the turn.
- Require the terminal stream outcome to be either:
  - a clean visible answer, or
  - a true unrecoverable runtime incompatibility after finalizer eligibility has been evaluated under the latest policy state.

## Reconnect and Terminality Invariant (NEW v2.5)
Hard rule:
- If backend loss triggers a reconnect or retry path, the stream must end in one of:
  - a clean visible answer,
  - a precise infrastructure failure class (`backend_lost`, `chat_route_unavailable`, `catalog_unavailable`, `ownership_mismatch`, or equivalent),
  - or a true unrecoverable runtime incompatibility.

Validation:
- Reject vague terminal transport copy when the system has enough evidence to classify the failure more narrowly.
- Reject reconnect flows that preserve `working`, `generate answer`, or ambiguous connection language after the backend has already refused the retried turn.
- Treat a post-reconnect turn as invalid when catalog or health looks recovered but the chat route still rejects the request and the user-visible surface does not say so precisely.

## Output Fidelity / Truncation Validation
Goal:
- Detect silent truncation where the stream ends “successfully” but the answer is incomplete.

Validation:
- Verify the answer channel contains the full intended string for “exact match” prompts.
- If the backend supports auto-continuation, verify you see the continuation status and additional `answer` chunks when the model ends early.
- If truncation appears in the UI, confirm whether truncation is:
  - Stream-side (missing `answer` chunks),
  - Persistence-side (saved message differs from stream),
  - Render-side (UI clipping/overlap).

## Failure Signals
- Run created but no `answer` tokens.
- Missing terminal event.
- Tool result emitted but absent from ledger.
- Stalled stream with open connection and no progress.
- Repeated `answer` chunks with negligible novelty gain.
- Visible answer stream contains template-role prefixes or hidden-reasoning markers.
- UI remains in `Sending...` or generating state while the stream only emits pathological repeated content.

## Non-Negotiable Constraints
- Do not use `backend_supervisor.log` as the required source of truth.
- Do not mark stream healthy from HTTP 200 alone.
- Do not mark a stream healthy if it is only emitting repeated, leaked, or semantically stagnant answer content.
- Do not mark a stream healthy if it only reaches reasoning/status output and never produces a visible final answer or typed terminal failure.
- Do not sign off a failed-turn UX if only the timeline is correct but the assistant message surface is still blank or misleading.
