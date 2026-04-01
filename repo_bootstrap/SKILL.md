---
name: repo_bootstrap
description: Bootstraps Project Free Energy environments with current multi-root skill
  topology and PFEMacOS runtime expectations.
version: 2.2.0
scope: local
portability_tier: strict_zero_leak
requires_env: []
project_profiles:
- PFEMacOS
---

# Repo Bootstrap Skill

## Profile Modes

- Default Profile (Generic): apply this skill in any repository using root discovery and environment-driven paths.
- Project Profile: PFEMacOS (Optional): enable PFEMacOS-specific behavior only when that project context is active.


## Purpose
Onboard a repo/workspace without legacy assumptions and with current runtime conventions.

## Current Bootstrap Truth
- Workspace-local skills live in `.agent/skills`.
- Global skills may exist in `~/.codex/skills` and optionally `~/.gemini/antigravity/skills`.
- PFEMacOS runtime uses BackendController dev/bundled modes, not `supervise.sh` as primary app launcher.

## Workflow
1. Verify monorepo structure and key app paths.
2. Ensure `.agent/skills` exists and required skills are present.
3. Mirror/sync selected global skills from `~/.codex/skills` when requested.
4. Validate launch readiness:
   - Dev mode prerequisites (`venv_312`, repo root detection).
   - Bundled mode prerequisites (`backend_runtime` resources).
5. Produce onboarding notes with health checks and known toggles (`PFE_BACKEND_MODE`, `PFE_BACKEND_RELOAD`).

## Workspace Goal Alignment (Additive v2.1)
Before executing bootstrap actions:
1. Ingest workspace-goal signals from The Watcher (`$skill_director`) when available.
2. Map bootstrap priorities to current workspace intent:
   - runtime bring-up
   - dependency readiness
   - portability stabilization
3. Emit a short "Goal-Aligned Bootstrap Plan" section with explicit rationale.
4. Keep all proposed changes additive and non-destructive.
5. Preserve strict portability by avoiding machine-specific paths and environment leakage.

## Locked Runtime And Release Bootstrap (NEW v2.2)
Bootstrap should validate and explain these repo truths when present:
- backend dependency source of truth is `pyproject.toml` plus a checked-in lockfile
- dev bootstrap, CI, and bundled runtime consume the same locked environment
- replay/eval scripts exist for regression safety
- launched-artifact smoke exists for packaged-runtime truth
- generated-project consistency is enforced when a generator such as `project.yml` is authoritative

Recommended bootstrap evidence:
- locked env bootstrap command
- backend test command
- Swift package test command
- Xcode app-target build command
- launched-artifact smoke command

## Recommended Core Skill Set
- `runtime-context-launcher`
- `uptime-reliability-sentinel`
- `autonomous-stream-validator`
- `log-detective-sre`
- `contract-parity-release-gate`
- `schema-parity-enforcer`

## Non-Negotiable Constraints
- Do not assume `~/.gemini` is the only source of global skills.
- Do not hardcode machine-specific absolute paths.
