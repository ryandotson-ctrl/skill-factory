# Hallucination Taxonomy v1

## Purpose
This taxonomy gives `hallucination-sentinel` a precise language for classifying failures without over-blaming the model when the root cause is actually routing, execution, or insufficient evidence.

## Classes

### `action_hallucination`
Definition:
- User-visible success claim without enough tool/result/verification proof.

Examples:
- "Moved 3 files" with no successful `fs.move`
- "Created Test folder" with no successful `fs.mkdir`

Non-examples:
- "I can't confirm that action succeeded"
- "I couldn't move the files because the destination isn't write-enabled"

Primary root causes:
- no-proof completion wording
- timeline/result mismatch
- simulated action prose

Primary owner skills:
- `model-ux-orchestrator`
- `qa-automation-engineer`
- `principal_code_auditor_worldclass`

### `evidence_hallucination`
Definition:
- A factual/current answer is presented as settled even though evidence breadth or source authority is insufficient.

Examples:
- Latest-version answer based on one blog
- Current-price answer with no finance-priority source

Non-examples:
- Official vendor release notes directly settling the version

Primary root causes:
- too few domains
- missing official source
- weak ranking policy
- stale snippets

Primary owner skills:
- `web-search-grounding-specialist`
- `model-ux-orchestrator`
- `qa-automation-engineer`

### `context_drop_hallucination`
Definition:
- A follow-up depends on prior turn state, but routing/query expansion loses the subject.

Examples:
- `fact check` no longer tied to the prior claim
- short follow-up move request loses previously listed entities

Primary root causes:
- weak follow-up expansion
- insufficient thread continuity heuristics

Primary owner skills:
- `web-search-grounding-specialist`
- `conversation-skill-evolution-director`
- `qa-automation-engineer`

### `confidence_miscalibration`
Definition:
- The wording is more certain than the evidence supports.

Examples:
- "Definitely" with stale/weak/conflicting evidence
- "Confirmed" when only one thin source exists

Primary root causes:
- insufficient abstain policy
- missing evidence-quality gating

Primary owner skills:
- `model-ux-orchestrator`
- `web-search-grounding-specialist`

## Nearby Non-Hallucination States

### `truth_guard_blocked_false_success`
Definition:
- The system correctly prevented an unverified success claim.

Interpretation:
- This is usually a guardrail success.
- Investigate phrasing quality and upstream executor gaps, but do not call it an `action_hallucination` unless the answer still falsely claimed completion.

### `deterministic_executor_gap`
Definition:
- The request was practically actionable, but deterministic resolution or execution failed before any tool succeeded.

Examples:
- recent listing showed the exact folders, but move routing still failed to execute

Interpretation:
- This is a routing/execution defect that often causes downstream truth-guard messaging.

## Evidence Sufficiency Defaults
- Current/latest/civic/fact-check: `3` distinct domains unless one authoritative first-party source directly settles the claim.
- Finance/current price: `2` distinct domains and at least one finance-priority source.

## Owner Mapping Summary
- user-visible truthfulness -> `model-ux-orchestrator`
- source breadth / ranking -> `web-search-grounding-specialist`
- missing regression coverage -> `qa-automation-engineer`
- severe correctness risk -> `principal_code_auditor_worldclass`
- repeated new pattern -> `conversation-skill-evolution-director`
