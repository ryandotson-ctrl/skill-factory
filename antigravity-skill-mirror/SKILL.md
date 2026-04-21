---
name: antigravity-skill-mirror
description: Audit and sync Antigravity global skills (~/.gemini/antigravity/skills)
  into Codex global skills (~/.codex/skills) with codex-canonical mirror governance,
  nested skill awareness, and optional publication-mirror drift reporting.
version: 1.2.0
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Antigravity Skill Mirror

## When To Use

- "Mirror Antigravity skills to Codex"
- "Sync Antigravity skills into Codex"
- "Do I have any Antigravity-only skills?"
- "Copy missing skills from Antigravity to Codex"

## Quick Start

- Dry-run report (no changes):
  - `python3 ${CODEX_HOME:-~/.codex}/skills/antigravity-skill-mirror/scripts/mirror_antigravity_skills.py`
- JSON dry-run report:
  - `python3 ${CODEX_HOME:-~/.codex}/skills/antigravity-skill-mirror/scripts/mirror_antigravity_skills.py --format json`
- Copy any missing Antigravity global skills into Codex global skills:
  - `python3 ${CODEX_HOME:-~/.codex}/skills/antigravity-skill-mirror/scripts/mirror_antigravity_skills.py --apply`
- Force Codex global skills to match Antigravity global skills (backs up then replaces):
  - `python3 ${CODEX_HOME:-~/.codex}/skills/antigravity-skill-mirror/scripts/mirror_antigravity_skills.py --apply --overwrite-existing`

Read `references/worked-examples.md` for the default dry-run, additive sync, and publication-mirror cases.
Use `references/report-contracts.md` for the canonical report shapes and `references/event-contracts.md` for Pulse Bus ingress and egress semantics.

## What This Does

1. Scans skills recursively in:
   - Antigravity global: `~/.gemini/antigravity/skills`
   - Codex global: `~/.codex/skills`
   - Local (informational): `.agent/skills` under the current workspace if present
   - Workspace mirror (informational): the current workspace root itself when it looks like a published skill mirror/export repo
2. Preserves nested skill identity by using relative skill paths, so hidden `.system/*` skills and runtime bundles are not silently dropped.
2. Computes diffs:
   - Which Antigravity global skills are missing from Codex global skills (copy candidates)
   - Which shared Codex/Antigravity skills have content drift and therefore require manual review unless overwrite is explicitly requested
   - Optional workspace-mirror drift so publication exports can be reviewed in the same pass
   - Union diffs (global + local) to catch "Antigravity-only" skills in the active workspace
3. If `--apply` is provided, copies missing skills from Antigravity global into Codex global.

The canonical dry-run contract is `MirrorReportV1`.
The canonical apply receipt is `MirrorApplyReceiptV1`.
When both codex/antigravity and codex/workspace-mirror are clean, report `MirrorAlignmentV1` so downstream skills can treat the mirror state as verified rather than merely unchecked.

Use The Watcher's `references/mirror_governance_v1.md` as the mirror-intent contract:
- `mirror_core` skills are expected to stay semantically aligned across codex and antigravity
- `codex_only` skills are reported but not treated as mirror failures
- `manual_review` skills should never be auto-overwritten without explicit human approval

## Safety Rules

- Default behavior is dry-run (prints a report and exits).
- Treat Codex as the canonical authoring root and Antigravity as the distribution mirror by default.
- Never deletes Codex skills.
- Never overwrites existing Codex skills unless `--overwrite-existing` is provided explicitly.
- When overwriting, it backs up the existing Codex skill directory under `~/.codex/skill_backups/antigravity-skill-mirror/`.
- Shared Codex/Antigravity drift is advisory by default and should be treated as manual review, not automatic replacement.

## Pulse Bus Contract

Ingress:
- `skill:antigravity-skill-mirror:requested`
- `skills:antigravity_mirror_requested`

Primary outputs:
- `skills:mirror_report_ready`
- `skills:workspace_mirror_drift_detected`
- `skills:mirror_alignment_verified`
- `skills:mirror_sync_applied`
- `skill_activity:antigravity-skill-mirror`

Use the event examples in `references/event-contracts.md` so mirror-state consumers can distinguish:
- audit-only reports
- publication-mirror drift
- verified clean alignment
- applied sync receipts
