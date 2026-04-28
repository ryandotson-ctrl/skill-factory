---
name: model-ux-orchestrator
description: Maintains truthful, premium assistant UX with timeline-first status communication
  and tool-confirmed action reporting.
version: 3.22.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles:
- PFEMacOS
---

# Model UX Orchestrator

## Profile Modes

- Default Profile (Generic): apply this skill in any repository using root discovery and environment-driven paths.
- Project Profile: PFEMacOS (Optional): enable PFEMacOS-specific behavior only when that project context is active.


## Mission
Preserve premium PFEMacOSApp response quality while ensuring every claim about actions is evidence-backed.

## Current UX Truth
- Assistant bubbles include run timeline state and rich formatted output.
- Composer should not be the primary status surface for model/tool activity.
- Send throttling and draftability are different truths; blocking a duplicate send must not disable text entry by default.
- Filesystem/tool actions must be reported from actual tool results, not simulated language.
- Unknown, unverified, loading, and blocked states are distinct UX truths and must never share the same copy or danger styling.
- Missing backend metadata must render as neutral uncertainty (`Available`, `Unknown`, `Needs verification`) rather than failure.
- Terminal failure events may arrive without a stable `run_id`; the visible timeline must still degrade to `Failed` from message-local evidence instead of disappearing.
- Transient refresh or decode failures must preserve the last known good visible state and report the failure on the correct surface rather than clearing truth or reusing unrelated error affordances.
- For PFEMacOS app-facing changes, SwiftPM/package success is necessary but not sufficient; the real Xcode app target must build before calling the work complete.
- Release-proof states are distinct truths: simulator-verified, device-installed, device-launched, and device-launch-blocked must not collapse into one success claim.
- Pathological generations (role-prefix echo, repeated loops, hidden reasoning leaks, garbage continuation) must fail closed at the user surface; raw junk is not an acceptable intermediate UX.
- Hidden reasoning, reasoning summary, and final answer are different truths even on answer-first surfaces; internal lane separation must preserve that distinction.
- `Filtered` means PFE removed reasoning or template scaffolding and preserved a usable final answer; it is not interchangeable with prompt echo, system echo, or hard failure.
- Raw infrastructure exceptions such as `BrokenPipeError`, socket failures, or backend ownership mismatches must never surface as normal answer-card content.
- Startup ownership uncertainty is its own truth state. It must not collapse into `0 installed models`, `No models found`, or destructive catalog failure copy before secure startup sync finishes.
- Once the system has enough evidence to finalizer-rescue a turn, the visible UX must not remain in `Working`, `Generate answer`, or stale pathology copy.
- Reconnect and chat-route uncertainty are distinct truths. `Backend Online`, `Lost connection`, `Reconnecting`, `Chat route unavailable`, and `Catalog unavailable` must not collapse into one generic connection message.
- Task model, helper/finalizer model, and picker selection are different truths. The visible UX must not imply that a hidden helper model replaced the user’s explicit selected model when it did not.
- Attachment-first analysis is a UX truth, not just a backend implementation detail. When the newest upload is the primary evidence, status and reasoning surfaces should make that obvious.
- Provider-lane truth is distinct from model truth. Backend MLX, optional Apple on-device providers, helper/finalizer models, and summarization helpers must not be collapsed into one generic assistant label.
- Latest-platform capability states such as Apple Intelligence eligibility, App Shortcut registration, and optional design-system adoption must remain typed, neutral when uncertain, and never be rendered as hard failure without proof.

## Trigger
- "The assistant claimed it moved/opened files but did not"
- "UX status feels confusing"
- "Formatting quality regressed"
- "The timeline said Completed but it actually failed"
- "Tables overlap / render twice / clip content"
- "It keeps repeating itself"
- "It is too chatty for simple questions"
- "Chain-of-thought leaked into the final answer"

## Workflow
1. User-surface truth audit:
   - Classify each visible state as verified success, verified blocked, loading, degraded, or unknown.
   - Never map missing/partial metadata to a destructive or failed UX state.
   - Preserve last known good state when a transient fetch/decode failure does not invalidate prior user-visible truth.
- During backend startup or ownership recovery, keep picker/store surfaces neutral and startup-specific; do not render absence as proved emptiness.
  - During reconnect after backend loss, keep the user-visible state precise: show reconnecting or chat-route recovery instead of implying the whole backend is gone when only turn acceptance is unavailable.
2. Timeline-first communication:
   - Keep operational status in assistant bubble timeline, not composer noise.
   - If a terminal failure arrives without full run metadata, degrade the existing message timeline to `failed` instead of dropping the event.
   - Infrastructure failures must be translated into typed degraded or failed states, not dumped as raw exception text in the answer bubble.
   - Attachment-analysis statuses must reflect the real path taken: received, indexed, searched, and generated. Do not imply direct reading when the system actually used indexed passages, and do not imply retrieval when only metadata was available.
3. Action truth enforcement:
   - Only confirm action success when tool result explicitly returns success.
   - If tool denied/failed, state exact reason and next step.
4. Input continuity:
   - Keep drafting surfaces editable during background work unless editing itself would corrupt state.
   - Disable repeat actions separately from disabling text entry.
5. Rendering quality checks:
   - Paragraph spacing, lists, links, tables, code/math readability.
   - Detect and quarantine repeated line loops, role-prefix echo, and hidden-reasoning spill before they accumulate into the visible transcript.
   - Split hidden reasoning or template scaffolding away from the candidate final answer before judging prompt echo, system echo, or failure states.
   - If a clean final answer survives sanitation, preserve it and keep degradation truth on the status surface instead of replacing the answer with a false failure banner.
6. PFEMacOS verification:
   - For app-facing Swift changes, run the actual Xcode app target build, not just `swift test`.
   - Verify the changed flow from the live user surface when feasible.
   - When the user asks for release readiness, prefer Release-build or archive evidence over Debug-only evidence.
   - When latest-SDK or latest-macOS work is involved, verify archive or launched-artifact truth before declaring platform integration complete.
   - Backend ownership, launcher, and transport fixes require live relaunch verification when feasible; package tests alone cannot prove the running app stopped binding to stale services.
   - If install succeeded but device launch was denied by device state such as `Locked`, report that as blocked verification rather than app failure.
   - If live verification was not performed, state that explicitly.
7. Final answer hygiene:
   - Remove tool/debug leakage from user-visible prose.
8. Response discipline:
   - For short factoid prompts, keep answers concise unless the user asks for detail.
   - Remove repeated paragraph/sentence loops before rendering.

## Task-Model Truth Doctrine (NEW v3.16)
- Separate these truths in user-visible and operator-visible surfaces:
  1. selected model
  2. task model used for the turn
  3. helper/finalizer model, if any
  4. reasoning summary generator
- Rules:
  - explicit user-selected turns must keep the selected model as visible task-model truth unless a typed incompatibility prevented the turn
  - helper or finalizer models must not be rendered as the task model on explicit turns
  - if a helper/finalizer was used, describe it as secondary render-path cleanup only
  - if indexed attachment passages were used, reasoning/status copy should say so plainly

## Provider Truth Doctrine (NEW v3.19)
- Keep these user-visible truths separate:
  1. primary runtime lane (for example local backend / MLX)
  2. optional on-device Apple lane
  3. helper/finalizer lane
  4. reasoning-summary generator
- Rules:
  - an optional Apple lane must be labeled as optional and additive, not as a silent replacement for the primary lane
  - unsupported, disabled, not-ready, and ready provider states must remain distinct
  - missing capability metadata must render neutrally, not as failure
  - provider badges should communicate what is actually powering the current action, not what merely exists on the system
  - App Intents and App Shortcuts registration truth should live on settings/inspector or capability surfaces, not be implied by general app health

## Causal Runtime Trace Doctrine (NEW v3.20)
- For tooling-heavy, grounded, or degraded turns, the primary trust surface should be a structured runtime trace, not summary prose alone.
- Prefer these user-visible runtime sections when they materially shaped the answer:
  1. `Route`
  2. `Evidence`
  3. `Tools`
  4. `Degradation`
  5. `Models`
- Keep these truths separate in the UI:
  - selected model
  - task model
  - helper/finalizer model
  - visible answer model
  - provider lane
- If a turn fails without a visible answer, the visible assistant surface must show the typed failure, not only the timeline.
- If attachment-grounded retrieval succeeded, status/reasoning surfaces should make it obvious that the answer came from indexed document evidence rather than generic memory or prior context.

## Single Transparency Surface Doctrine (NEW v3.21)
- The default assistant bubble should expose one inline transparency primitive, not multiple overlapping ones.
- Prefer this order of truth:
  1. final answer
  2. one inline `How I answered` card when grounding, tools, or document verification materially shaped the answer
  3. full operational trace in Inspector or an advanced operator surface
- Do not render separate parallel inline disclosures for:
  - `How I answered`
  - `Summary Reasoning`
  - detailed runtime trace
  when a single structured transparency card can carry the same truth.
- Keep the inline transparency card consumer-facing:
  - verified evidence summary
  - compact field/value grid
  - short human explanation when needed
- Keep raw tool names, model-lane drama, and debugger-style trace detail out of the default bubble unless the user has explicitly entered an advanced inspection surface.

## Grounded Briefing UX Doctrine (NEW v3.22)
- A constrained or fallback briefing must still feel useful, not evasive.
- If a requested section cannot be fully supported, fill that section with a calm thin-coverage clarification instead of omitting it or dumping source titles.
- Do not let a complete-looking outline hide missing substance.
- User-facing structured answers must prefer:
  1. extracted facts
  2. explicit uncertainty
  3. short next-best clarification of what remains thin
  over:
  - repeated headlines
  - generic geopolitical filler
  - internal route or schema anxiety
- Reasoning or transparency summaries must never use scary operator phrasing such as:
  - `could not confidently classify this turn with a valid route schema`
  - `runtime failed route arbitration`
  - `provider returned unsupported evidence shape`
  unless the user is in an explicitly advanced inspection surface.
- Replace operator-language leakage with calm, truthful user copy such as:
  - `Coverage was limited for part of this briefing, so I kept those sections cautious.`
  - `I found strong evidence for some parts of your question and thinner evidence for others.`

## Structured Answer Readability Doctrine (NEW v3.22)
- When a user asks for a table, briefing, or exact structure, the visible answer must either:
  1. render that structure cleanly, or
  2. fall back to a readable alternative that still honors the request
- Half-rendered structure is a UX failure.
- Treat these as stop-ship answer-quality issues:
  - raw markdown table syntax leaking as the visible table when a richer path is expected but broken
  - headings with low-information filler repeated beneath them
  - section shells that visually imply completeness while content remains generic

## Send Immediacy Doctrine (NEW v3.21)
- The first visible reaction to `Return` or `Send` is a product truth requirement.
- The app must append the user message and assistant placeholder before async preflight work such as:
  - backend readiness probes
  - model probes
  - workspace refresh/setup
- Show immediate local progress copy:
  - `Working...`
  - `Reading your document...`
  - `Looking at your attachment...`
  or equivalent user-facing wording.
- Preflight failure may update the placeholder into a typed failure state later, but it must not create dead air first.
- Treat these as stop-ship regressions:
  - pressing send produces no visible change for a noticeable beat
  - the composer clears but no assistant placeholder appears
  - attachment sends do not acknowledge the attachment path immediately

## Composer Surface Simplicity Doctrine (NEW v3.21)
- The composer should read as one integrated dock, not a dock containing a second bright input slab.
- Prefer emphasis through focus ring, border, spacing, and motion rather than a heavy nested white field.
- Attachment shelf, text input, and primary send affordance should feel like parts of one control surface.
- A nested bright rectangle inside an already elevated dock is a UX smell and should be treated as a quality issue, not just a styling preference.

## Latest-macOS UX Doctrine (NEW v3.19)
- When adopting a newer macOS design system, apply native styling selectively and preserve typed truth over fashion.
- Neutral Tahoe-style chrome must not blur:
  - unknown vs failed
  - available vs installed
  - optional lane vs primary lane
- New platform affordances such as glassy surfaces, richer sheets, or settings scenes are only correct if they still preserve explicit product truth.

## Rescue Terminality Rule (NEW v3.14)
- If task-model or repair phases complete and a safe finalizer lane exists, the user-visible turn must move to a terminal answer or a true unrecoverable incompatibility.
- Do not leave the user in `Working` or `Generate answer` once finalizer rescue is available.
- Do not let stale pathology copy outrank a valid finalizer-rescued final answer.
- Finalizer rescue must preserve terminal answer truth, not just backend correctness.

## Final Answer Hygiene Invariants (Stop-Ship)
- No reflective/meta self-talk in user-visible prose (for example: "I'm confused", "looking at the context provided", planning narration).
- No duplicated paragraphs or repeated sentence loops in final output.
- For short fact questions, default to a concise answer (no multi-paragraph rambling).
- Repeated role labels (`Assistant:`, `User:`, `System:`) or template scaffolding must not appear as the user-visible answer.
- Repeated `Assistant:` or `Model:` lines inside hidden reasoning must never be promoted into the answer lane just because they were the last labeled span.

## Answer-First Reasoning Lane Doctrine (NEW v3.11)
- Separate these truths internally when a runtime can emit reasoning:
  1. final user-visible answer
  2. reasoning summary
  3. raw or hidden reasoning
- On answer-first surfaces, keep reasoning hidden by default and preserve the final answer whenever a clean answer lane survives sanitation.
- `Filtered` is valid only when scaffolding or hidden reasoning was removed and a usable answer remains.
- `prompt echo` or `system prompt echo` is valid only when the surviving final-answer lane still echoes the prompt or instructions, or when no usable final answer remains.
- Downgrade unstable reasoning lanes to safer answer-only behavior before surfacing a user-facing failure when the final answer is still recoverable.

## Mobile Local-Generation UX Doctrine (NEW v3.16)
- Mobile local-generation flows must expose a visible in-flight state immediately; a blank assistant bubble is a stop-ship UX failure.
- When local generation starts, the transcript should show a truthful placeholder such as `Thinking...` or equivalent local-generation copy before any answer text arrives.
- If the runtime later produces a usable answer, replace the placeholder with the final answer instead of appending a second assistant bubble.
- If the runtime fails, replace the placeholder with the terminal degraded or failed state rather than leaving the transcript visually empty.
- Preserve the distinction between:
  - generation in progress
  - answer repair in progress
  - degraded but usable answer
  - terminal failure

## Mobile Composer Compactness Doctrine (NEW v3.17)
- On phone-sized layouts, focus alone must not force the composer into a large multiline state.
- The empty composer should stay compact and single-line until draft length or explicit newlines require expansion.
- Placeholder alignment must be centered in collapsed state and shift to multiline/top-aligned behavior only after expansion is justified by content.
- Attachment controls, primary input, and trailing actions should share the same visual baseline in collapsed mode.
- Empty-space-heavy composers that visually dominate the lower third of the screen are a correctness issue, not a stylistic preference.

## Mobile Header Truth Doctrine (NEW v3.18)
- On compact/mobile chat surfaces, model state should be lightweight and subordinate to the conversation surface.
- Avoid large banner-like model pills when an inline selector will communicate the same truth more clearly.
- Header controls that live on the same row, such as hamburger/menu affordances and model selectors, must align visually before sign-off.
- Status badges that repeat low-signal runtime states in cramped header space should be removed or relocated unless they materially improve user decisions.

## Rendering Invariants (Stop-Ship)
State semantics:
- Unknown/unverified state must never render as a failure label, failure copy, or destructive red treatment.
- Missing backend fields must map to a neutral UX state until incompatibility or failure is explicitly proven.
- For PFEMacOS model/catalog surfaces, `available`, `installed`, `blocked`, `vision-only`, and `unknown` must remain visually distinct.

Tables:
- Never render the same table twice (native table + raw markdown duplicate).
- Never allow overlapping text or clipped cell content.
- If the “rich table” renderer cannot fully render, fall back to a readable plain markdown table or a list (do not half-render).
- Prefer readable wrapping and/or horizontal scroll over truncation.

Long text and numbers:
- No silent truncation inside cells (e.g., `Ram 1500` -> `Ram 150`, `$47,850` -> `$47,85`).
- If the backend provides an exact-match or “return exactly” prompt, the UI must display the full string without eliding characters.

Code/math blocks:
- Must preserve monospace alignment and spacing.
- Must not collapse multi-line blocks into a single clipped line.

## Timeline Truth Invariants
- If generation fails, the timeline must show a failed state (not “Completed”).
- “Completed” is only valid when the backend emitted a successful terminal run state.
- A missing `run_id` on a terminal failure event is not permission to drop the failure state from the user-visible timeline.
- A quarantined/pathological generation must surface as degraded or failed, never as a normal completed assistant response.
- If the newest attachment was the dominant evidence source, timeline/status copy must not imply the model ignored the upload or answered from prior conversation context.

## Input Continuity Invariants
- Disabling send does not imply disabling the composer.
- Keep text entry available during streaming unless editing would violate a verified backend constraint.

## Error Surface Truth Invariants
- Refresh failures, delete failures, and session/auth failures must not share the same user-visible error label or panel.
- When a refresh fails but the app still has verified prior state, preserve that state and show the failure separately.
- Raw Python, socket, or IPC exceptions must not render directly inside the answer card; they belong in typed failure surfaces and diagnostics only.
- Startup or ownership sync uncertainty must not render as `No models found`, `0 model(s)`, or a blocked picker until the startup budget is exceeded and emptiness is actually verified.
- Reconnect or chat-route rejection must not render as a generic “Could not connect to the server” if the backend is alive but the current turn was rejected for a narrower infrastructure reason.

## PFEMacOS Build Truth Invariants
- For app-facing Swift changes, `swift test` passing is not enough to claim the app is fixed.
- Require a successful real app-target build (`xcodebuild` or equivalent Xcode target build) before sign-off.
- When the bug is user-visible, prefer live flow verification from the app surface over model-only or package-only confidence.
- When the fix changes backend ownership or launch-path logic, require a fresh app relaunch check before claiming the stale-runtime UX is resolved.
- When the fix changes reconnect, chat-acceptance, or startup convergence behavior, require a launched-app check that a real turn is accepted after startup and after backend interruption.

## Action Truth Invariants (Filesystem + Artifacts)
- No “Created a PDF / moved a file / opened a file” unless a tool call exists in the timeline AND the tool result confirms success.
- For create operations, show the destination path in the tool result preview and confirm the file exists (verification).

## Non-Negotiable Constraints
- Never fabricate completion for filesystem/model/tool actions.
- Prefer concise, structured Markdown with citations/links when relevant.
- Never allow hidden-reasoning artifacts to appear in user-visible output.
- Never let live streaming render obviously pathological output indefinitely just because the transport is still alive.
- Never expose raw infrastructure exception text as if it were a user-facing assistant response.

## Pathology Quarantine Contract (NEW v3.9)
When the answer lane shows any of the following:
- repeated identical or near-identical lines
- template-role echo (`Assistant:`, `User:`)
- hidden reasoning / planning leakage
- nonsense continuation that adds no user value

Required behavior:
1. Stop rendering raw pathological chunks as normal answer content.
2. Preserve a truthful degraded-state explanation in the timeline or operator surface.
3. Keep the user-visible answer clean, minimal, and non-repetitive.
4. Prefer a typed `degraded`, `quarantined`, or `failed` UX state over pretending the response completed successfully.

## Bridge Output Sanitization (No Mock/Scaffold Leakage)
User-visible responses must never expose bridge scaffolding or mock-mode internals.

Block and sanitize patterns such as:
- `[mock-*]` prefixed payloads
- raw system scaffolding (`SYSTEM:`, `Tooling`, tool manifest dumps)
- untrusted metadata/object dumps rendered directly to users

If sanitation is triggered:
1. Preserve user intent and provide a clean, actionable response.
2. Mark route degradation in timeline/operator state (not in user prose unless needed).
3. Emit internal diagnostic evidence for debugging.

## Response Utility Floor
Operational replies must remain useful, concise, and non-repetitive by default.

Rules:
1. Lead with the direct answer for short prompts.
2. Avoid repeated summaries or filler loops.
3. If required facts are missing, ask one targeted clarification or provide one concrete next action.
4. Prefer structured outputs (short bullets/table) when reporting runtime/tool state.
5. Default concise mode unless the user explicitly asks for deep detail.

## No-Proof Claim Blocklist
Never allow completion language unless proof exists in tool/timeline evidence.

Block user-visible claims when proof is missing:
- "done", "completed", "success", "finished"
- "is now open/closed/restarted/deployed"
- "I already did that"

Required replacement behavior:
1. State `not yet verified`.
2. Trigger the required tool call or ask one direct confirmation prompt.
3. Report next action in one line.

## Tool-Confirmed Completion Contract
For any operational action response:
1. Include tool/result evidence internally before final prose.
2. If tool result is absent, timeout, or error, return failure/blocked status only.
3. If user asks for re-check, run explicit verification tool call before asserting state.
