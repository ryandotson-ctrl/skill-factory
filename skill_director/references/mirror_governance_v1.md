# Mirror Governance v1

Use this contract when deciding whether a skill should mirror across roots.

## Mirror Intent Classes
- `mirror_core`: should exist in codex and distribution mirrors when contracts stay equivalent
- `codex_only`: canonical in codex and not automatically mirrored unless explicitly promoted
- `agents_owned`: owned by the agents root; codex may observe but should not silently absorb
- `manual_review`: semantic drift or root-specific behavior requires a human decision

## Default Decision Rules
1. Codex remains the canonical authoring root unless explicitly overridden.
2. Antigravity is the default distribution mirror for `mirror_core` skills.
3. Workspace publication mirrors should reflect codex truth but exclude runtime residue.
4. If a skill becomes root-specific, classify it `manual_review` instead of force-syncing it.

## Evidence To Include
- current canonical root
- intended mirror targets
- drift type: none, additive, metadata, or semantic
- preservation note explaining what must not be lost during sync
