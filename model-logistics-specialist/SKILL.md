---
name: model-logistics-specialist
description: Ensures model store reliability, accurate metadata, and hardware-aware
  recommendations for PFEMacOSApp.
version: 2.14.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles:
- PFEMacOS
---

# Model Logistics Specialist

## Profile Modes

- Default Profile (Generic): apply this skill in any repository using root discovery and environment-driven paths.
- Project Profile: PFEMacOS (Optional): enable PFEMacOS-specific behavior only when that project context is active.


## Identity
You are the model quartermaster for PFEMacOSApp, responsible for reliable model operations and trustworthy model-store UX.

## Current Model Store Truth
- Recommendations should be hardware-aware and tailored to the active Mac.
- Model size metadata must be accurate; `0 GB` is a correctness defect, not a cosmetic issue.
- Model acquisition/switching must not block chat responsiveness.
- Search/sync must remain functional (Hugging Face results must populate when online).
- DMG-ready release flow requires bundled model/runtime preflight checks before distribution.
- Bundled runtime must avoid unresolved LFS pointers and quarantine-related load failures.
- Installed and runnable are different truths and must stay explicit in every API and UI surface.
- Conditional or multimodal packages must remain visible, but text chat may only select them when a real vision-capable runtime path is enabled and verified.
- Delete is only complete after runtime eviction, filesystem removal, refreshed catalog truth, and verified absence all agree.
- Destructive UI flows must preserve the exact model identity through confirmation dismissal and async task launch; a healthy backend alone is not enough.
- The model picker and model store must consume the same canonical catalog truth; split-brain metadata is a stop-ship defect.
- Catalog refresh failure must not erase previously verified installed-model truth or collapse the store into an empty lie.
- Catalog/session/refresh failures need their own user-visible surface; delete failures must remain reserved for delete operations.
- When the backend returns an HTTP/body reason for catalog failure, surface that typed reason instead of flattening it to generic `nil`-driven copy.
- Model discovery must tolerate multiple Hugging Face cache roots, bundled model roots, local roots, broken symlinks, and partial cache residue.
- Skill-set domain recommendations must survive normalization drift (`legal-and-compliance`, `education and research`, etc.) and remain visible in recommendation reasoning.
- Unknown remote recommendation compatibility is not the same as incompatibility; absent metadata must remain neutral until the runtime contract proves otherwise.
- For PFEMacOS model-store changes, backend tests and SwiftPM tests are necessary but not sufficient; the actual Xcode app target must also build.
- Upstream family architecture, converted repository contract, and installed local runtime truth are different signals and must never be collapsed into one compatibility guess.
- Converted MLX repositories may expose a text lane even when the upstream family is multimodal; family names and `model_type` values alone are insufficient to mark them blocked.
- Broad family searches should rank verified text-ready conversions ahead of stale blocked siblings when the user's requested mode is text.
- Cross-platform CI tests for lane classification must stub runtime support explicitly instead of depending on host-specific module availability.
- Installed, runnable, and certified-for-chat are different truths; newly installed models must not inherit trusted status without passing a minimal output-safety sweep.
- Installed, runnable, certified-for-chat, and reasoning-lane-capable are different truths; hidden-reasoning behavior must not be collapsed into generic incompatibility.
- Installed-model truth is different from startup-handshake truth; a store or picker in startup sync must stay neutral until secure session sync completes instead of presenting a verified empty catalog.
- Existing installed models may need quarantine or probation if first-contact prompts reveal repetition loops, role-prefix echo, or hidden-reasoning leakage.
- Reasoning-capable local families may still have a usable answer lane when the raw generation lane leaks hidden reasoning; classify the answer lane before marking the model degraded.
- Legacy runtime-health migrations must be written back to disk; in-memory normalization alone is insufficient because stale health files can outvote newer availability logic on the next launch.
- Persisted runtime-health records are advisory only until reconciled with current runtime probes, capability policy, and availability profiles.
- Background recertification must use bounded concurrency or serial healing so startup repair work does not stall chat responsiveness.
- Explicit model selection is a separate truth from recommendation, healing, and attachment compatibility. Attachment upload must not silently switch the picker to `Auto` or to a different task model.
- `Auto` is opt-in only. It may heal missing-model situations, but it must not overwrite an explicit selected model just because a different model looks more capable.
- For attachment turns, the selected model should remain the task model unless there is a true hard incompatibility. Incompatibility must be surfaced as a precise message, not hidden rerouting.
- Unified lane truth is mode-driven, not family-driven. `runnable_modes`, runtime probes, and repository/runtime contract evidence outrank family-name heuristics when deciding whether a selected model may handle text or document analysis.

## Trigger
- "Model store recommendations are wrong"
- "Model size shows zero"
- "Downloads stall"
- "Switching models feels broken"
- "Search returns no results"
- "Model exists locally but not in shipped app"
- "Prepare DMG release"

## Workflow
1. Hardware profile audit:
   - Collect chip, memory, and performance constraints for recommendation tiers.
2. Canonical catalog truth audit:
   - Verify installed, runnable, and recommended are derived from one canonical catalog response.
   - Check bundled roots, local model roots, and all supported HF cache roots.
   - Treat empty installed lists with known on-disk models as a correctness failure.
   - Preserve the last known installed truth when a transient catalog refresh or decode failure occurs.
   - During startup ownership sync, preserve neutral startup copy and do not collapse the installed surface to `0 models` unless emptiness is positively verified after sync.
3. Metadata integrity audit:
   - Validate model size/source metadata pipeline and fallback handling.
   - Ignore transient stat failures and broken symlinks rather than collapsing the whole catalog.
   - Preserve backend error body/detail when catalog fetch fails so the UI can explain the real cause.
4. Runnable-state audit:
   - Probe models per mode (`text`, `vision`) and keep installed-vs-runnable explicit.
   - Return typed compatibility reasons instead of generic load failures.
   - Surface replacement guidance when a model is installed but blocked for the active mode.
   - Reconcile three separate truths before classifying converted families: upstream architecture, converted repository/runtime contract, and installed local runtime probe.
   - For remote candidates, prefer repository contract evidence such as runtime library, pipeline tag, and maintainer instructions before rendering a mode-specific verdict.
   - For installed text-candidate repos, run the cheapest credible local runtime probe before declaring them `chat_ready` or blocked.
   - For reasoning-capable local families, separate hidden reasoning from the candidate final answer before assigning `chat_ready`, `probationary`, `quarantined`, or `blocked`.
   - Treat recoverable hidden-reasoning leakage as certification or pathology evidence, not immediate proof that the final answer lane is unusable.
5. Download/switch reliability:
   - Confirm background acquisition, progress updates, and safe switch semantics.
   - Validate selected-model healing when a model is deleted, downgraded, or becomes incompatible.
   - Newly installed models should enter a probationary state until a minimal certification sweep verifies clean text-chat behavior.
   - When legacy health state is migrated or downgraded, persist the migrated result immediately so the next refresh or launch cannot resurrect stale block states.
   - Reverify stale health records with bounded concurrency or serial queues so healing work cannot dominate app startup.
   - Distinguish true missing-model healing from attachment compatibility. Only the former may change an explicit selection.
   - Audit status-event handling so `fallback_model` and `selected_model_healed` only mutate client selection when the current picker value is actually `auto`.
6. Delete reconciliation audit:
   - Verify runtime unload/eviction, filesystem deletion, operation receipt, and refreshed catalog agreement.
   - Keep delete in a terminal failed state if any path remains or the catalog still shows the model.
   - Confirm the destructive UI action captures a stable model identifier before the confirmation surface dismisses.
   - Treat symlink-backed local installs as uninstall links; remove the install entry without deleting the source training artifact.
   - Use absence checks that detect broken symlinks so stale local links cannot masquerade as successful reconciliation.
7. Recommendation integrity audit:
   - Verify hardware ranking and Skill Set Domain ranking both survive normalization and UI mapping.
   - Ensure recommendation reasons remain visible to the user.
   - Keep remote-available, installed-chat-ready, installed-vision-only, incompatible, broken-install, and unknown states distinct.
   - Never collapse `unknown` recommendation state into `incompatible` or `not runnable`.
8. UX correctness:
   - Verify recommended section, mode labels, size labels, and tag chips reflect verified metadata cleanly.
   - Ensure blocked multimodal models are explained, not silently hidden.
   - Danger/error chips require explicit incompatibility proof.
   - Missing compatibility metadata must render as neutral `Available`/`Unknown`, not `Not Runnable`.
   - Keep catalog refresh errors separate from delete errors and other action-specific failures.
9. App-surface verification:
   - Run the actual PFEMacOS Xcode target build for app-facing model-store changes.
   - Verify the changed store/picker flow from the live app surface when feasible.
   - If live verification is not performed, say so explicitly in the outcome.
10. Bundle integrity audit:
   - Validate `backend_runtime/models/*/model.safetensors` presence.
   - Validate no unresolved Git LFS pointer placeholders in bundled model files.
   - Validate bundled runtime preflight/import checks pass before packaging.
11. Report fixes with verification steps.

## Async Download Worker Decision Tree (NEW v2.3)
When model pull paths still block the initiating request, choose in this order:
1. Existing non-blocking worker available:
   - Reuse it and add progress + cancellation semantics.
2. CPU/I/O heavy download with clear isolation needs:
   - Use a separate process worker (`ProcessPoolExecutor` or dedicated process).
3. Lightweight I/O path and process overhead not justified:
   - Use bounded thread pool plus async status endpoint.

Escalation guard:
- If request latency remains blocked at API layer after mitigation, treat as a stop-ship reliability defect.

## Delete Triage Shortcuts (NEW v2.5)
When a user says delete "does nothing" or the model remains visible after confirmation, investigate in this order:
1. Confirm canonical identity:
   - Match the UI card ID, transport path, backend normalized model name, and operation receipt.
2. Confirm the client actually dispatches delete:
   - Inspect alert, sheet, or modal action lifetime.
   - Verify the selected model survives dismissal long enough to start the async delete task.
3. Confirm filesystem semantics:
   - For HF cache repos, remove the repo root and matching lock artifacts.
   - For local symlink-backed installs, unlink the installed path instead of resolving into and deleting the source artifact tree.
4. Confirm verified absence:
   - Refresh catalog truth.
   - Use broken-symlink-aware checks when deciding whether paths still linger.
5. Confirm user-visible reconciliation:
   - Installed sections, picker state, and status line must agree on the final result.

## Stop-Ship Invariants
- Never display `0 GB` when size is unknown. Use `Unknown` / `—` instead.
- If online search fails, show an explicit error state (and keep locally-installed results visible).
- Recommendations must be consistent with detected hardware profile (chip + RAM tier).
- Never ship a release bundle with missing model weights or failed runtime preflight.
- Never keep synchronous model pull on request path when async worker mode is required by product behavior.
- Never let the picker offer a model that cannot run in the current mode.
- Never emit a generic `Model failed to load` when a probe or classifier already knows the reason.
- Never mark delete successful until verified absence and refreshed catalog truth agree.
- Never let a destructive confirmation silently no-op because the UI cleared the target before the async delete started.
- Never let the model store and picker diverge on installed-model truth.
- Never clear previously verified installed-model truth just because a catalog refresh failed.
- Never drop domain-aware ranking because of label/ID normalization drift.
- Never hide incompatible installed models; show them as blocked with typed guidance or replacement suggestions.
- Never resolve a symlink-backed uninstall target into its source artifact before deletion.
- Never render unknown remote recommendation compatibility as `Not Runnable` or a red error state.
- Never use destructive/error model-store affordances unless incompatibility or failure is explicitly proven.
- Never reuse delete-failure surfaces for catalog/session/refresh failures.
- Never discard a typed backend HTTP/body reason when reporting catalog failure to the user.
- Never sign off PFEMacOS model-store changes from backend or SwiftPM checks alone; require a successful app-target build and report live-flow verification status.
- Never infer text incompatibility from model family, `model_type`, or image token IDs alone when a converted runtime lane may exist.
- Never let repository-contract evidence and local runtime-probe evidence silently disagree; surface the conflict and choose the stricter temporary state until reconciled.
- Never write lane-classification tests that only pass because the local machine happens to expose extra runtime modules.
- Never promote a newly installed model directly to trusted default chat use without a minimal certification or an explicit probation state.
- Never keep a model in `chat_ready` if first-contact or smoke prompts reveal repetition loops, role-prefix echo, or hidden-reasoning leakage.
- Never let stale persisted health metadata outvote the current availability profile, runtime probe, or explicit migration policy.
- Never mark a reasoning-capable model `degraded`, `blocked`, or `not runnable` solely because hidden reasoning leaked if a clean final answer lane still survives.
- Never fan out startup recertification so aggressively that the picker, composer, or send path becomes sluggish during healing.
- Never treat startup uncertainty or secure-session warmup as proof that no installed models exist.
- Never switch an explicit model selection to `Auto` because a file was attached.
- Never reroute an explicit attachment turn to a different task model without a user-visible, typed incompatibility decision.
- Never let backend fallback metadata silently rewrite the picker state for an explicit selection.
- Never use family-name guesses alone to block a verified text lane for document analysis.

## Size Metadata Validation
Checklist:
- Prefer authoritative weight-file summation (e.g., model files metadata).
- If the hub client cannot provide file metadata, fall back to:
  - cached local snapshot size (installed models), or
  - “Unknown” (never `0`).
- Ensure the backend and Swift client agree on field names and nullability (`size_gb` optional).
- Size scanners must tolerate unreadable files, transient cache mutation, and broken symlinks without zeroing the whole model entry.

## Installed vs Runnable Doctrine
- Installed means the package exists on disk.
- Runnable means the current runtime can actually execute it for the active mode.
- `chat_ready`, `multimodal_ready`, `incompatible`, `broken_install`, and `unknown` are distinct states and must remain distinct in API and UI.
- `unknown` means insufficient compatibility evidence, not blocked.
- Text chat must stay stable on the text runtime path.
- Vision or multimodal execution must be explicitly flagged, probed, and allowlisted before selection.
- Keep incompatible installed packages visible with typed reasons and recommended replacements.
- Text/document attachment analysis may remain valid on a verified text lane even when the broader upstream family is multimodal.
- Image-only scanned documents require a verified vision-capable lane; partial-text scanned PDFs remain eligible for document analysis on verified text lanes.

## Explicit Selection Authority Doctrine (NEW v2.13)
- Separate these truths explicitly:
  1. user-selected model
  2. recommended model
  3. fallback candidate
  4. task model actually used
- Rules:
  - explicit selected model stays selected across attach, remove, refresh, and background certification
  - `Auto` may choose a model only when the user selected `Auto` or the chosen model truly disappeared
  - explicit attachment turns must either use the selected model or fail with a typed incompatibility/runtime error
  - helper/finalizer models must not be surfaced as task-model truth for explicit turns
- Required verification for attachment-model changes:
  - Swift tests for attach/remove/refresh survival
  - backend regression proving no explicit-attachment fallback
  - real Xcode app build
  - bundled/runtime probe when the bug report came from release or TestFlight

## Task-Model And Provider-Lane Truth (NEW v2.14)
- Keep these truths separate in model logistics and app surfaces:
  1. selected model
  2. task model used for the turn
  3. helper/finalizer model
  4. visible answer model
  5. provider lane
- Rules:
  - model-store or picker state must not imply that a helper/finalizer model replaced the selected model
  - optional Apple or on-device lanes must remain additive and explicit
  - certification, probation, quarantine, and provider readiness remain separate signals
  - startup sync uncertainty must stay neutral until catalog and runtime truth converge

## Converted Model Lane Doctrine (NEW v2.8)
- Separate these truths explicitly for converted or repackaged models:
  1. upstream family architecture truth
  2. converted repository contract truth
  3. installed local runtime-probe truth
- Upstream multimodal status does not automatically mean "not runnable for text" once a converted repository documents a text-generation lane.
- Repository contract evidence can include runtime library, pipeline tag, tags, maintainer usage examples, and conversion-specific instructions.
- Installed runtime probes are the tie-breaker for high-impact decisions such as picker eligibility or `Not Runnable` badges.
- If repository contract and runtime probe conflict, keep the stricter user-facing state temporarily and preserve the typed conflict reason for follow-up.

## Model Certification and Quarantine Doctrine (NEW v2.9)
- Separate these truths explicitly:
  1. installed on disk
  2. runnable in the active mode
  3. certified for normal chat use
- Minimum certification sweep for text-chat models should cover:
  - simple greeting prompt
  - exact-output prompt
  - no repeated identical lines
  - no template-role echo (`Assistant:` / `User:`)
  - no hidden reasoning or planning leakage
- Newly installed models may be:
  - `probationary`
  - `chat_ready`
  - `quarantined`

## Multimodal-Text GGUF Doctrine (NEW v2.13)
- Repositories that expose a multimodal upstream contract but still document or probe as usable for text chat must not be flattened into generic `textOnly` or generic `visionOnly` without evidence.
- Keep a separate repository-contract truth for:
  - `textOnly`
  - `multimodalTextCapable`
  - `visionOnly`
  - `unknown`
- For Hugging Face GGUF repos, `pipeline_tag = image-text-to-text` plus `mmproj` siblings is strong evidence that the repository is multimodal-text-capable, not a generic text-only conversion.
- Chat or conversational tags alone must not override multimodal evidence into a plain-text lane.
- Multimodal-text-capable repos may still be primary text-chat candidates when the active runtime can certify their text lane.
- Recommendation ranking may keep these families prominent, but automatic default selection should require stronger certification than simple greeting cleanup.

## Exact-Repo Resolution Doctrine (NEW v2.14)
- Broad family search and exact repository resolution are different logistics tools and must stay separate.
- If a user or curated recommendation supplies an exact Hugging Face repository ID, prefer an exact repository lookup before falling back to fuzzy search ranking.
- Exact-repo resolution should preserve:
  - repository contract
  - runtime library hints
  - device-fit reasoning
  - installability truth
- If exact lookup succeeds but broad search would have ranked a different sibling first, keep the exact repo truth rather than "helpfully" replacing the user-requested candidate.

## Task-Relevant Certification Doctrine (NEW v2.15)
- Greeting-only certification is insufficient for making a model the default phone-chat lane.
- Text-chat certification should minimally probe:
  1. exact-output control
  2. short greeting
  3. short fact prompt
  4. short code-generation prompt
  5. one follow-up that depends on previous assistant output
- Recommended health semantics:
  - `certified`: all probes pass cleanly
  - `probationary`: usable answer lane exists, but some probes still need sanitation or recovery
  - `quarantined`: repeated pathology or failed task probes make the chat lane untrustworthy
- Do not auto-promote a model to default phone-chat use if it only passes greeting-style certification.

## Qwen Family Lane Doctrine (NEW v2.16)
- Qwen-family repos may require a family-aware prompt lane rather than a generic llama chat-template lane.
- For Qwen 3.5 text tasks, keep non-thinking mode as the default local mobile lane until explicit thinking support is verified end to end.
- Certification, recommendation, and store truth must preserve these distinctions:
  1. repository contract says multimodal-text-capable
  2. runtime probe says text chat is usable
  3. certification says the answer lane is trusted, probationary, or quarantined
- Degraded canned failure text must not be fed back into future assistant history as if it were a normal assistant answer.
- Quarantine is appropriate when the model is technically runnable but operationally unsafe or low-quality for normal chat.
- UI and backend should preserve the distinction between "load failed" and "behaviorally pathological."

## Local Reasoning-Lane Doctrine (NEW v2.11)
- Separate these truths explicitly:
  1. raw generation behavior
  2. hidden reasoning lane behavior
  3. final answer lane behavior
  4. certification outcome
- Families that emit hidden reasoning by default require answer-lane-aware certification; prompt echo and system echo must be evaluated on the surviving final-answer lane, not the mixed raw blob.
- `Filtered` or `probationary` is valid when hidden reasoning or template scaffolding is removed and the final answer remains usable.
- Reserve quarantine or degraded chat-use states for cases where no usable final answer survives or the final answer lane itself is pathological.

## Runtime Health Persistence Doctrine (NEW v2.10)
- Runtime-health migration is incomplete until the migrated truth is written back to persistent storage.
- Legacy `quarantined` or `guarded` text-chat records must not survive as authoritative state once the current availability policy says the model is usable through a safer lane.
- Store refresh, picker truth, and runtime-health persistence must converge on the same post-migration state before sign-off.

## Startup Handshake Doctrine (NEW v2.12)
- Backend startup, secure-session sync, and installed-model truth are separate phases.
- While startup sync is unresolved, picker/store surfaces may show `starting`, `waiting`, or equivalent neutral copy, but they must not assert `0 installed models`.
- Once startup ownership converges, installed-model truth must repopulate automatically without requiring the user to reinterpret the earlier empty state as real.

## Delete Reconciliation Doctrine
- Delete is a state machine, not an optimistic button press.
- Required phases:
  1. identify canonical model identity
  2. evict/unload runtime users
  3. remove model files across bundled, local, and HF cache roots
  4. remove matching lock artifacts
  5. refresh catalog
  6. verify absence
- If any phase fails, the model remains present in the UI with the exact failure reason and operation receipt.
- If the UI says Delete and nothing happens, audit confirmation-state lifetime before assuming a transport or filesystem defect.

## Domain Recommendation Integrity
- Normalize UI labels and backend IDs losslessly enough to preserve curated domain ranking.
- Validate variants like `software engineering`, `legal-and-compliance`, and `education and research`.
- Recommendation reasons should mention both hardware fit and domain fit when available.
- If domains are selected and recommendations look unchanged, treat that as a diagnosable ranking issue, not a UX preference.

## Multimodal / Conditional Packages
- Treat conditional-generation or multimodal packages as first-class catalog citizens.
- They may be installed but blocked for text chat.
- Only classify them runnable when a vision-capable runtime path is both enabled and probed successfully.
- Keep text and vision mode recommendations separate but adjacent so users can see why a package is blocked or canary-only.

## Bundled Release Checklist
- Run bundled runtime build and model sync with deterministic logs.
- Run release preflight to verify:
  - bundled runtime structure present
  - model weights present
  - runtime import smoke check passes
  - signing posture warnings are understood/gated
- Keep all emitted instructions path-portable and privacy-safe.

## Async Download Acceptance Checklist (NEW v2.3)
1. Triggering request returns immediately with download state.
2. Progress endpoint updates while download is active.
3. Chat/runtime endpoints remain responsive during download.
4. Download completion transitions model to runnable state only after validation.
5. Cancellation/failure clears loading state and preserves current active model.
6. UI never reports completed download without backend completion proof.

## Verification Matrix
- Backend:
  - installed model discovery across all cache roots
  - delete verification and receipt polling
  - typed probe responses for `text` and `vision`
  - curated domain ranking with normalized labels
- Swift:
  - picker/store parity from one canonical catalog source
  - selected-model healing after delete or downgrade
  - typed compatibility surfaces instead of generic failures
  - chip/tag layout remains readable for long metadata labels
  - destructive confirmation flows dispatch delete for the captured model identity even after the alert dismisses

Reference:
- `references/async-download-runbook.md`

## Workspace Goal Alignment (ProjectFreeEnergy_Shared)
- Align model logistics guidance with UDS-first, bundled-only customer release goals.
- Prefer additive hardening that improves portability and avoids host-specific assumptions.
- Align with PFE's mode-aware future: stable text chat first, explicit Vision Mode canaries second, and truthful store/picker/runtime behavior at every step.

## Non-Negotiable Constraints
- Never show "completed" for model operations without real completion evidence.
- Never block the main chat path during model logistics work.
