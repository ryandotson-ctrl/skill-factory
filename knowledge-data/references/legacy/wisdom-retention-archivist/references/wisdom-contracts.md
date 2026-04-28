# Wisdom Contracts

Use these contracts to keep wisdom archival deterministic and reusable.

## WisdomEntryV1
- `topic`
- `source_kind`: postmortem, recommendation, audit, or experiment
- `lesson`
- `evidence`
- `scope`
- `reusability`: global, profile-bound, or workspace-bound
- `sanitization_notes`

## RecallCandidateV1
- `entry_id`
- `relevance_score`
- `why_relevant`
- `carry_forward_as`: guardrail, recommendation input, or anti-regression note

## Digest Policy
- Prefer grouped lessons over transcript-like dumps.
- Keep ledgers append-only.
- Preserve provenance without leaking private paths or secrets.
