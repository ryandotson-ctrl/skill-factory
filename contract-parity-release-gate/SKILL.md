---
name: contract-parity-release-gate
description: Deterministic multi-contract release gate that aggregates parity checks across chat, search, rag, model lifecycle, and training domains before migration cutovers.
version: 1.3.0
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Contract Parity Release Gate

## Purpose
Provide one go/no-go contract for release readiness when multiple subsystem parity gates must pass together.

## Use When
- You need a single migration cutover decision across many contracts.
- You want deterministic release-blocking output with clear blockers.
- You need additive, portability-safe gating artifacts for CI or audit trails.

## Inputs
1. Contract parity reports from upstream skills/tools.
2. Optional policy overrides (required domains, blocker tolerance).
3. Optional release context metadata (target version, branch, environment class).

## Outputs
1. `ContractParityGateResultV1` with:
   - `status` (`pass`, `warning`, `blocker`)
   - `domain_results[]`
   - `blocking_domains[]`
   - `release_recommendation`
2. Human-readable summary for release notes/checklists.

## Workflow
1. Ingest domain parity evidence.
2. Normalize domain states into deterministic statuses.
3. Apply gating policy:
   - any blocker domain -> global blocker
   - warnings only -> warning
   - all pass -> pass
4. Emit machine-readable result and remediation order.

## Launched Artifact Parity Rule (NEW v1.1)
For public release or launch-ready claims, parity must include the launched artifact, not only audited source or package-level tests.

Required evidence:
1. The running backend artifact matches the expected audited source/build path for the release candidate.
2. The launched app can complete startup ownership sync and surface installed-model truth.
3. The launched app/backend can accept at least one real chat turn after startup.
4. If release proof cites bundled behavior, the bundled/runtime artifact must be the one actually exercised.

Blocking policy:
- Mark the gate `blocker` when source-level tests pass but the launched artifact serves a stale, divergent, or non-chat-ready backend path.

## Attachment Intelligence Parity Rule (NEW v1.2)
For document-analysis or attachment-first assistant claims, parity must include real attachment understanding, not only upload success or attachment acknowledgment.

Required evidence:
1. Upload extraction truth:
   - the uploaded attachment is classified correctly
   - extracted text, extraction confidence, and route strategy are preserved
2. Ingest truth:
   - `rag.ingest` uses the real extracted payload for retrieval-backed or sectioned documents
   - metadata-only placeholders do not replace extracted payloads when extracted text exists
3. Retrieval truth:
   - `rag.search` can retrieve attachment-grounded passages for the uploaded document under the active workspace scope
   - fresh-upload turns filter back to the uploaded document source before broad workspace recall
4. Verification truth:
   - document verification/analyzer steps read the extracted document payload and can produce verified or partial claims from that evidence
5. User-visible truth:
   - if attachment understanding fails, the app surfaces a typed failure
   - if attachment understanding succeeds, the answer demonstrates grounded document knowledge instead of generic metadata talk

Blocking policy:
- Mark the gate `blocker` when the system can upload and acknowledge a document but cannot retrieve or verify the extracted text for the same turn.
- Mark the gate `blocker` when workspace-scoped retrieval hides a document that was ingested into a different scope or default-only scope.

## Source-vs-Packaged Divergence Rule (NEW v1.3)
- Package-level tests and source-level checks do not outrank contradictory packaged-artifact evidence.
- Treat this as a first-class blocker when:
  - SwiftPM or unit tests pass
  - but `xcodebuild`, archive validation, or launched-artifact runtime truth fails
- Required evidence for app-facing release claims:
  1. source/package tests
  2. real app-target build
  3. launched-artifact runtime check when the change affects startup, routing, attachments, model selection, or visible answer flow

## Document Truth Fixture Rule (NEW v1.3)
- For attachment/document changes, parity must include fixture assertions on the actual user-visible answer, not only tool success.
- Required fixture classes:
  - billing statement
  - invoice
  - contract
  - report/research-style document
- Required prompt coverage should include common deictic user wording:
  - `what is this about`
  - `please tell me what this is about`
  - `tell me about this in great detail`
- Blocking policy:
  - mark the gate `blocker` when the visible answer loses the primary verified field while the summary card or underlying verifier still has it
  - mark the gate `blocker` when invoice-vs-billing-statement identity flips incorrectly in packaged/runtime verification

## Required Domains (Default Policy)
- `chat_runtime`
- `search_grounding`
- `rag`
- `model_lifecycle`
- `training_pipeline`
- `launched_artifact_parity`
- `attachment_intelligence_parity` when the release or change touches upload, document analysis, RAG, or grounded PDF understanding

## Non-Negotiable Constraints
1. Never mark `pass` when any required domain is missing.
2. Never suppress blockers without explicit override evidence.
3. Never include host-specific absolute paths in output.
4. Keep all recommendations additive and rollback-aware.

## References
- `references/contracts-v1.md`
- `scripts/run_gate.py`
