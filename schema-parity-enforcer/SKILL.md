---
name: schema-parity-enforcer
description: Enforces schema parity across backend Python models and client contracts,
  including Swift Codable types used by PFEMacOSApp.
version: 2.4.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles:
- PFEMacOS
---

# Schema Parity Enforcer

## Profile Modes

- Default Profile (Generic): apply this skill in any repository using root discovery and environment-driven paths.
- Project Profile: PFEMacOS (Optional): enable PFEMacOS-specific behavior only when that project context is active.


## Identity
You prevent contract drift across backend and clients.

## Current Contract Truth
- PFEMacOSApp depends on Swift `Codable` contracts for chat, workspaces, and run timeline events.
- Backend emits mixed REST + SSE payloads that must remain type-safe across Python and Swift (and TS where used).
- Streaming answers are delivered as multiple `answer` fragments and must be lossless when concatenated.
- If the backend introduces degraded, quarantined, or pathology-specific events for unsafe model output, Swift and backend must agree on their shape and semantics before shipping.

## Trigger
- "Type mismatch"
- "Event field missing"
- "Run timeline broke"
- "Workspace API shape changed"
- "Runs show Completed even when generation failed"
- "New SSE event broke the app"
- "Model got quarantined but the client didn't understand it"

## Workflow
1. Inventory backend contracts:
   - Pydantic/response models and SSE event payloads.
2. Inventory client contracts:
   - Swift models (`ChatEvent`, run timeline, workspace payloads), plus TS interfaces when relevant.
3. Diff and classify:
   - Missing fields, nullability mismatch, enum/value drift, numeric/string coercion issues.
4. Propose synchronized changes and compatibility notes.
5. Ingest contract docs bundle when present and align schema findings with contract gates.

## Contract Bundle Ingestion (NEW v2.2)
When `docs/contracts/` exists:
1. Build a contract index from markdown contracts.
2. Map each runtime/schema check to a contract gate.
3. Emit parity result by contract domain (chat, search, rag, model lifecycle, training, files, sessions).
4. Classify each domain as:
   - `pass`
   - `warning`
   - `blocker`

Use:
- `references/contracts-index.md`
- `scripts/check_contract_parity.py`

## Priority Contracts
- `run.*` event payloads
- Workspace and roots APIs
- Tool call/result payloads
- Model metadata payloads used in model store
- Filesystem tool names (e.g., `fs.open`, `fs.move`, `fs.create_pdf`) must be treated as opaque strings (do not enum-freeze without migration).
- Any typed output-pathology, degraded, or model-quarantine events and fields

## Failure Semantics Contract (Stop-Ship)
Run lifecycle:
- Successful completion must end in `run.finished` with `status=completed`.
- Failed generation/tooling must end in `run.error` with an error string.

Step lifecycle:
- Steps must end with `run.step.finished` and `status` must be `completed` or `failed`.

Tool lifecycle:
- `run.tool.call` must have a matching `run.tool.result` (or a failed step with a recorded error).

## Stream Concatenation Contract (Stop-Ship)
- Client must be able to concatenate all `answer` fragments into the exact final assistant message.
- No client-side trimming/overlap logic may drop legitimate boundary characters (especially numeric suffixes and currency).

## Output Pathology Contract (NEW v2.3)
When the product introduces typed handling for unsafe model output:
- The backend must emit a distinct, documented event or field for degraded/pathological/quarantined output.
- The client must not infer this state from ad-hoc string matching alone when a typed contract exists.
- Timeline and answer-surface semantics must agree on whether the run is `completed`, `degraded`, or `failed`.

## Turn-State And Provenance Contract (NEW v2.4)
When the backend introduces an explicit orchestrator turn model, backend and client contracts must stay aligned on:
- `TurnState`
- `ToolExecutionStep`
- `EvidenceRef`
- `GroundingClaim`
- `DegradationState`
- `AnswerProvenance`

Required parity checks:
- selected/task/helper/visible-answer model identities keep the same names and semantics across Python and Swift
- provider-lane truth remains typed and additive
- `turn.started`, `turn.route`, `evidence.added`, `degradation.state`, `answer.provenance`, and `turn.completed` stay schema-compatible on the wire
- failed `turn.completed` payloads preserve terminal failure truth instead of forcing the client to infer from unrelated fields

## Non-Negotiable Constraints
- Backend and Swift contracts are equally first-class.
- Do not ship schema changes without compatibility or migration notes.
- Do not declare parity complete without contract-gate evidence for each active domain.
- Do not let timeline truth and terminal assistant-message truth diverge because one event family is typed and the other is inferred.
