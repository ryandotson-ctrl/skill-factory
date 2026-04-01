---
name: antigravity-skill-mirror
description: Audit and sync Antigravity global skills (~/.gemini/antigravity/skills)
  into Codex global skills (~/.codex/skills). Copies missing skills and produces a
  diff report.
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
- Copy any missing Antigravity global skills into Codex global skills:
  - `python3 ${CODEX_HOME:-~/.codex}/skills/antigravity-skill-mirror/scripts/mirror_antigravity_skills.py --apply`
- Force Codex global skills to match Antigravity global skills (backs up then replaces):
  - `python3 ${CODEX_HOME:-~/.codex}/skills/antigravity-skill-mirror/scripts/mirror_antigravity_skills.py --apply --overwrite-existing`

## What This Does

1. Scans skills in:
   - Antigravity global: `~/.gemini/antigravity/skills`
   - Codex global: `~/.codex/skills`
   - Local (informational): `.agent/skills` under the current workspace if present
2. Computes diffs:
   - Which Antigravity global skills are missing from Codex global skills (copy candidates)
   - Union diffs (global + local) to catch "Antigravity-only" skills in the active workspace
3. If `--apply` is provided, copies missing skills from Antigravity global into Codex global.

## Safety Rules

- Default behavior is dry-run (prints a report and exits).
- Never deletes Codex skills.
- Never overwrites existing Codex skills unless `--overwrite-existing` is provided.
- When overwriting, it backs up the existing Codex skill directory under `~/.codex/skill_backups/antigravity-skill-mirror/`.
