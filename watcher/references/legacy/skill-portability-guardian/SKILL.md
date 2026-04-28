---
name: skill-portability-guardian
description: Audits and hardens skill libraries for portability and privacy safety.
  Applies deterministic autofixes for path/user leakage, absolute links, and host-specific
  assumptions while preserving project-specific behavior via optional profiles.
version: 1.6.0
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles:
- PFEMacOS
---

# Skill Portability Guardian

## Profile Modes

- Default Profile (Generic): apply this skill in any repository using root discovery and environment-driven paths.
- Project Profile: PFEMacOS (Optional): enable PFEMacOS-specific behavior only when that project context is active.


## Purpose

Make skills safe to share and reuse across machines and projects.

This skill audits active skill roots, applies deterministic portability/privacy fixes, creates backups before any change, and emits verifiable reports with before/after evidence.

## Trigger

Use this skill when the user asks to:

- "portability harden skills"
- "sanitize skills"
- "de-leak skills"
- "make skills reusable on other systems"
- "remove personal paths from skills"

## Mandatory Upstream Context

Before running fixes, consult:

1. `$skill_director` for ecosystem scope and root coverage.
2. `$omniscient-skill-cataloger` for complete inventory.

## Workflow

1. Inventory target roots:
   - Codex global: `${CODEX_HOME:-~/.codex}/skills`
   - Antigravity global: `~/.gemini/antigravity/skills` (if present)
   - Agents global: `~/.agents/skills` (if present)
   - Workspace local: `<workspace>/.agent/skills` (if present)
   - Use The Watcher's `references/ecosystem_contract_v1.yaml` for nested-skill identity, root roles, and backup/runtime classification.
2. Audit for portability/privacy violations using deterministic regex rules from `references/portability_rules.yaml`.
3. If mode is `apply`:
   - Create root-scoped backups first.
   - Apply only allowlisted file types.
   - Never mutate `_p0_backups` or `.backups` trees.
4. Re-scan and enforce strict policy.
5. Emit JSON + Markdown reports with file-level evidence when apply mode or explicit artifact output is requested.

## Command

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/skill-portability-guardian/scripts/skill_portability_guardian.py \
  --mode apply \
  --roots codex,antigravity,agents,local \
  --workspace-root "$(pwd)" \
  --strict-zero-leak true
```

## Modes

- `--mode audit`: report only (no mutations)
- `--mode audit`: read-only audit of the real on-disk state; writes no reports unless explicit report paths or `--write-report-artifacts` are provided
- `--mode apply`: audit + safe autofix (default)
- `--mode snapshot`: strict read-only health snapshot; writes no reports, no scope-map artifacts, and no skill-file changes

## Safety Rules

1. Backup before every file mutation.
2. Allowlist only: `SKILL.md`, `.py`, `.sh`, `.md`, `.json`, `.yaml`, `.toml`, `.yml`.
3. Preserve specialized behavior by replacing hardcoded machine assumptions with parameterized forms.
4. Keep PFEMacOS guidance in optional profile blocks when present.
5. Skip missing roots without failing.
6. Treat machine-local generated watcher state as runtime artifacts, not portable skill source.

## Outputs

- JSON report: machine-readable summary + evidence.
- Markdown report: human-readable findings, fixes, and residuals.

If strict mode is enabled and leak patterns remain after apply, the run exits non-zero.

## Compatibility Handling: Frontmatter Schema Drift

When validators and existing skills disagree on allowed frontmatter fields:

1. Classify the result as a compatibility finding, not an automatic destructive fix.
2. Do not auto-delete unknown or legacy frontmatter keys from existing skills.
3. Preserve required trigger fields (`name`, `description`) and preserve additional keys unless the user explicitly requests normalization.
4. Record schema-drift findings in output reports with:
- file path,
- validator expectation,
- observed keys,
- recommended remediation path (manual review or profile-aware validator update).
5. Treat trigger-only frontmatter as compatible when `SKILL.md` keeps only `name` and `description` and the skill also provides `agents/openai.yaml`.
6. Do not auto-add portability contract fields to trigger-only frontmatter solely to satisfy a stricter validator if sidecar metadata is present.
7. Treat portability contract fields declared under `metadata` as valid contract fields when assessing completeness or deciding whether autofix is needed.

## Canonical Root and Mirror Governance

When auditing mirrored global skills:

1. Treat codex (`~/.codex/skills`) as the canonical authoring root unless the user explicitly overrides it.
2. Treat antigravity (`~/.gemini/antigravity/skills`) as a distribution mirror when the skill intent is equivalent.
3. Preserve root-specific profile blocks, sidecar metadata, and compatibility shims when they do not change semantic intent.
4. When drift is semantic rather than additive, classify the result as `manual review` instead of force-syncing it.

## Mirror Closure Decision Contract

For mirrored skills, classify follow-up action as exactly one of:

1. `mirror`: codex is newer or more complete and antigravity should be synchronized additively.
2. `hold`: differences are metadata-only or intentionally root-local.
3. `manual review`: semantic intent diverged and a human decision is required before sync.

Every mirror recommendation must include:
- canonical root,
- mirror targets,
- drift type,
- portability note explaining what must be preserved during sync.

## Safe Autofix Boundaries (Do Not Rewrite Semantics)

Autofixes must preserve meaning while improving portability/privacy:

1. Allowed semantic-safe fixes:
- absolute path/user leakage normalization,
- host-specific literal replacement with environment-driven placeholders,
- machine-specific execution hints moved to optional profile blocks.

2. Disallowed semantic-changing fixes:
- rewriting operational intent,
- collapsing distinct safety rules,
- removing compatibility metadata without explicit approval,
- altering trigger meaning in `description`.

3. When a potential fix is semantically ambiguous:
- report and stop in audit mode for that item,
- do not apply speculative rewrites.
