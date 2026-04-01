---
name: issue-tracker-guardian
description: Portable autonomous issue lifecycle manager that detects, classifies, deduplicates, tracks, and closes issues with evidence gates across GitHub or local ledgers.
version: 2.2.0
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Issue Tracker Guardian 2.0

## Purpose
Use this skill to manage issues end-to-end with guarded autonomy:
- detect likely bugs/features from repo/runtime signals
- classify + label consistently
- deduplicate against open issues
- update issues with new evidence
- close only when evidence and verification gates pass
- reopen when regressions are detected

This skill is reusable across projects and does not require project-specific paths.

## Trigger Phrases
- "file a bug"
- "track this issue end-to-end"
- "reconcile open and closed issues"
- "auto-manage backlog"
- "close resolved issues automatically"

## Required Skill Coordination
Before major issue triage or mass reconciliation:
1. consult `$omniscient-skill-cataloger` for ecosystem awareness
2. consult `$skill_director` when deciding canonical/mirrored scope behavior

## Operating Modes
Use `scripts/issue_guardian.py`.

### Modes
- `scan`: read-only signal and issue analysis
- `ingest`: normalize new issue candidate from user/log/test/git input
- `reconcile`: full lifecycle pass (detect/create/update/reopen and optional close)
- `close`: evaluate closure gates for open issues and close eligible ones
- `report`: summarize tracker state and lifecycle decisions

### Tracker Backends
- `github`: uses GitHub Issues via `gh` CLI
- `local`: uses local `issues.md` + `.issue-guardian/state.json`
- `auto` (default): uses GitHub when available/authenticated, otherwise local

### Label Behavior (GitHub)
- Applies classification labels on open/update flows.
- Automatically creates missing labels (when repository permissions allow), then attaches them.
- If label creation is blocked by repo policy/permissions, lifecycle continues without failing hard.

## Default Workflow
1. Detect signals from user/test/log/git/issue sources.
2. Classify into `bug|enhancement|chore|question` with severity.
3. Build deterministic fingerprint.
4. Deduplicate against open issues.
5. Create new issue or update existing issue with evidence.
6. Evaluate closed issues for regression reopen.
7. Evaluate closure gates for open issues.
8. Emit report + events.

## Noise Suppression and Safe Autonomy
To prevent backlog spam and false-positive issue creation:
- Treat Git signals as evidence-only by default; do not open issues from raw `git status` / commit listings.
- Block issue creation for progress/status-update language (for example: "work in progress", "fix applied", "tests passed", "build complete").
- Cap issue opens per run (`max_new_issues_per_run`) to avoid runaway automation.
- Prefer duplicate-update over create whenever fuzzy/title/fingerprint matching is strong.

When sharing implementation progress, use `--mode report` (or `scan`) instead of `reconcile`.

## Closure Gate Policy (Strict)
An issue can close only when all are true:
1. linked fix evidence exists (commit or PR reference)
2. mapped verification checks pass
3. no fresh conflicting failure signals in recent window

If checks are unavailable and policy disallows test-less close, closure is blocked.

## Commands
### Reconcile pass (recommended default)
```bash
python3 scripts/issue_guardian.py \
  --mode reconcile \
  --tracker auto \
  --workspace-root . \
  --input-source user \
  --input-source tests \
  --input-source logs \
  --input-source issues \
  --periodic-window-hours 24 \
  --report-json .issue-guardian/last-report.json \
  --report-md .issue-guardian/last-report.md
```

### Progress/update-only pass (no issue mutation intent)
```bash
python3 scripts/issue_guardian.py \
  --mode report \
  --tracker auto \
  --workspace-root . \
  --report-json .issue-guardian/last-report.json \
  --report-md .issue-guardian/last-report.md
```

### Ingest a specific report
```bash
python3 scripts/issue_guardian.py \
  --mode ingest \
  --tracker auto \
  --message "App freezes after clicking Send" \
  --evidence "stack trace ..." \
  --input-source user
```

### Safe dry run
```bash
python3 scripts/issue_guardian.py --mode reconcile --dry-run true --strict true
```

## Optional Project Config
Optional config path:
- `.issue-guardian/config.yaml`

See:
- `references/issue_taxonomy.yaml`
- `references/lifecycle_policy.yaml`
- `references/templates.md`

Supported optional keys:
- `classification_rules`
- `label_map`
- `path_ownership`
- `verification_map`
- `duplicate_policy`
- `closure_policy`

## Event Contract (Pulse Bus v2)
### Inputs
- `issue:scan_requested`
- `issue:ingest_requested`
- `issue:reconcile_requested`
- `qa:test_failed`
- `git:push_complete`
- `log:anomaly_detected`

### Outputs
- `issue:opened`
- `issue:updated`
- `issue:duplicate_detected`
- `issue:resolution_candidate`
- `issue:closed`
- `issue:action_blocked`

## Evidence-First Event Intake Contract
Treat incoming runtime and git signals as evidence, not automatic mutation permission:

1. `qa:test_failed`, `log:anomaly_detected`, and `git:push_complete` may trigger reconciliation or reporting, but must not bypass issue-creation or closure gates.
2. For mutation-heavy flows, prefer `report` or `scan` when evidence quality is low.
3. When route ownership is ambiguous, let orchestration guidance resolve ownership before opening or closing issues.

## Constraints
1. No hardcoded personal paths, usernames, or host assumptions.
2. No issue closure without explicit closure gate evidence.
3. Deterministic, auditable behavior: every action must appear in report output.
4. Prefer update-over-create when duplicate confidence is high.
