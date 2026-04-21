---
name: storage-hygiene-cleanup-orchestrator
description: "Dynamic, session-aware storage guardian that audits hot vs warm vs cold\
  \ paths, plans safe delete/offload actions, governs external SSD archival on `\uF8FF\
  e`, and imports legacy cold-storage state into one registry."
metadata:
  version: 2.0.0
  portability_tier: strict_zero_leak
  scope: global
  requires_env: []
  project_profiles: []
---

# Storage Hygiene Cleanup Orchestrator

This is the canonical storage skill.

It must:
- classify storage from live signals, not calendar-specific rules
- use current session, thread, workspace, worktree, model, and lock/PID context
- mine the active thread family's rollout history so any conversation can protect the files, workspaces, and caches it is actively touching
- infer goal workspaces from the conversation itself, so saying "I'm working on Skill Factory" or "keep Project Free Energy safe" can protect related artifacts even without absolute paths
- distinguish `hot`, `warm`, and `cold`
- plan `delete_now`, `offload_manifest`, `review_first`, and `protect`
- treat `e` as a governed storage tier, not just a blind destination
- keep all new offloads manifest-only by default

## Core commands

Audit:
```bash
python3 scripts/storage_hygiene.py audit \
  --workspace "$PWD" \
  --json-out "$PWD/artifacts/storage_guardian_report.json" \
  --md-out "$PWD/artifacts/storage_guardian_report.md" \
  --include-external \
  --external-root "/Volumes/e/ Home/Archive/ssd-guardian-portable"
```

Apply only low-risk deletes:
```bash
python3 scripts/storage_hygiene.py apply \
  --plan "$PWD/artifacts/storage_guardian_report.json" \
  --actions delete_now \
  --confirm APPLY
```

Apply cold manifest offloads:
```bash
python3 scripts/storage_hygiene.py apply \
  --plan "$PWD/artifacts/storage_guardian_report.json" \
  --actions offload_manifest \
  --confirm APPLY
```

Restore:
```bash
python3 scripts/storage_hygiene.py restore \
  --source-path "$HOME/.codex/sessions/2026/04/01" \
  --confirm RESTORE
```

Import compatible legacy cold-storage trees:
```bash
python3 scripts/storage_hygiene.py import-legacy \
  --external-root "/Volumes/e/ Home/Archive/ssd-guardian-portable"
```

## Decision rules

- `hot`: currently active or strongly referenced. Never auto-delete or auto-offload.
- `warm`: recent or loosely referenced. Prefer `review_first`.
- `cold`: stale and unreferenced. Eligible for `delete_now` or `offload_manifest` depending on type.

Default windows:
- `hot_days = 14`
- `warm_days = 45`

Primary signals:
- current cwd match
- current live thread and spawned subagent family
- thread `updated_at` from `.codex/state_5.sqlite`
- rollout/session JSONL history for the active thread family, including user-requested paths and tool-touched workdirs/files
- goal-object inference from user messages and thread titles matched against discovered workspace and worktree aliases
- session day recency under `.codex/sessions`
- workspace git activity
- worktree cleanliness and recency
- workspace config/env model references
- lockfiles, PID files, and legacy live symlinks
- existing registry and restore history

## Safety rules

- Never execute mutations without explicit confirmation.
- Revalidate every candidate at apply time. A stale plan must not delete or offload something that has become hot.
- Never create new live symlink offloads by default.
- Training artifacts are protected or review-first by default.
- Apple-managed stores and personal media remain protected.
- If context discovery fails, degrade toward `review_first` or `protect`, never toward aggressive deletion.

## Contracts

The audit output is `StorageGuardianPlanV2`.
The apply result is `StorageGuardianApplyResultV2`.
Use `references/contracts.md` for the current shapes.
