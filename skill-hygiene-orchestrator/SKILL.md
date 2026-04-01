---
name: skill-hygiene-orchestrator
description: Audits and de-duplicates skills across Codex (~/.codex/skills), Antigravity
  (~/.gemini/antigravity/skills), and workspace local (.agent/skills). Keeps the newest
  version, backs up old copies, and syncs roots.
version: 1.1.0
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Skill Hygiene Orchestrator

## Overview

Keep your skill libraries clean and consistent: detect duplicate skills (including `_` vs `-` naming collisions), pick the newest copy, back up older versions, and sync the winning version across roots.

## When To Use

- \"Do I have duplicate skills?\"
- \"Deduplicate my skills\"
- \"Sync my skills between Antigravity and Codex\"
- \"Keep the newest version of each skill\"
- \"Clean up underscore vs hyphen skill duplicates\"

## Quick Start

Dry run (report only):

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/skill-hygiene-orchestrator/scripts/skill_hygiene.py
```

Apply changes (backs up then syncs/dedupes):

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/skill-hygiene-orchestrator/scripts/skill_hygiene.py --apply
```

Force legacy full-directory replacement sync:

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/skill-hygiene-orchestrator/scripts/skill_hygiene.py --apply --sync-strategy replace_dir
```

Restrict to specific roots:

```bash
python3 ${CODEX_HOME:-~/.codex}/skills/skill-hygiene-orchestrator/scripts/skill_hygiene.py --apply --roots codex,antigravity
```

## What It Does

1. Inventory skills from:
   - Codex global: `~/.codex/skills` (or `$CODEX_HOME/skills`)
   - Antigravity global: `~/.gemini/antigravity/skills`
   - Workspace local: `<workspace>/.agent/skills` (if present)
2. Detect duplicates:
   - Same skill name across roots with different payload (different version/content)
   - `_` vs `-` collisions (example: `orchestration_sentinel` vs `orchestration-sentinel`)
3. Pick the winner per skill:
   - Highest semantic version if available, else newest file timestamps
4. Apply fixups (only with `--apply`):
   - Backup first
   - Default: targeted payload sync (only managed files) to avoid accidental drift
   - Optional legacy mode: full directory replacement (`--sync-strategy replace_dir`)
   - Archive duplicate directories that collide by normalized name

## Safety Rules

- Dry-run is the default.
- No permanent deletes: old versions are moved into a timestamped backup folder.
- Overwrites happen only after backup succeeds.

## Merge Safety: System Skills and Metadata Variants

When deduplicating skills across roots, enforce metadata-aware merge safety:

1. Never collapse two skills solely because frontmatter shapes differ or one has extra metadata keys.
2. Treat `.system` skills as protected class:
- require stricter merge confidence,
- preserve system-specific guidance unless explicitly superseded by a newer authoritative copy.
3. If content and intent are equivalent but metadata schemas differ:
- prefer preserving the richer instruction body,
- preserve compatibility metadata unless an explicit normalization policy is provided.
4. If ambiguity remains, mark the pair for manual review instead of auto-merging.

## Winner Selection Evidence Contract

For each dedupe/merge decision, emit explicit evidence in report output:

1. Candidate set:
- source root and path for each candidate,
- content hash/signature,
- version/timestamp signals used.

2. Decision rationale:
- why the winner was selected (version precedence, recency, or authoritative root),
- whether metadata schema differences were detected,
- whether manual review was required or bypassed.

3. Safety trace:
- backup location for replaced copies,
- actions taken (copied, archived, skipped),
- post-merge verification status.
