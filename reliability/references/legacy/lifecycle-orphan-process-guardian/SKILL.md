---
name: lifecycle-orphan-process-guardian
description: Detect and prevent orphan background process regressions after app shutdown for any project. Use when users report high memory or CPU after exit, when introducing or changing process managers, lifecycle hooks, backend launchers, hot-reload workers, or shutdown logic, and before releases to verify launch and quit leave zero unintended child processes.
---

# Lifecycle Orphan Process Guardian

## Overview

Audit and harden process lifecycle behavior so app exit actually tears down spawned workers.
Verify static lifecycle contracts and run an end-to-end launch/quit check with optional remediation.

## Workflow

1. Gather runtime config:
- Resolve target commands from explicit flags first.
- Optionally load a profile from `references/profiles.json`.
- Keep everything path-agnostic and environment-driven.

2. Run static lifecycle checks (if configured):
- Confirm lifecycle/termination hooks exist.
- Confirm shutdown path exists and is reachable.
- Confirm process stop logic includes child-process cleanup and force-kill fallback.

3. Run runtime liveness check:
- Snapshot baseline matching processes.
- Execute launch command.
- Execute shutdown command.
- Assert post-shutdown residual matched processes == 0 (excluding baseline).

4. Optional remediation (`--mode apply`):
- Send graceful termination to residual process tree.
- Escalate to force kill if still alive after grace window.
- Re-scan and report final state.

5. Emit evidence:
- Write JSON + Markdown report when paths are provided.
- Return non-zero exit when strict checks fail.

## Quick Commands

Generic audit:
```bash
python3 scripts/lifecycle_orphan_guardian.py \
  --mode audit \
  --launch-cmd "<start command>" \
  --shutdown-cmd "<stop command>" \
  --process-match "uvicorn .*backend.main:app" \
  --process-match "my-worker-name"
```

Generic apply (safe remediation):
```bash
python3 scripts/lifecycle_orphan_guardian.py \
  --mode apply \
  --launch-cmd "<start command>" \
  --shutdown-cmd "<stop command>" \
  --process-match "my-process-pattern" \
  --report-json "./orphan-process-report.json" \
  --report-md "./orphan-process-report.md"
```

Profile-driven run:
```bash
python3 scripts/lifecycle_orphan_guardian.py \
  --profile pfe_macos_swiftui \
  --mode audit \
  --workspace-root "<repo root>" \
  --skip-runtime
```

## Profile System

Profiles are optional adapters for known project shapes. They must be additive and never required.
Use `references/profiles.json` for sample profile definitions.
Each profile rule can optionally include `targets` (workspace-relative file paths) or `target_pattern` (regex) so checks run only where they should.

## Output Contract

The script returns:
- `0` when all enabled checks pass.
- `2` when lifecycle findings remain.
- `1` for execution/usage errors.

## Constraints

1. Never hardcode user-specific paths or host-specific usernames in skill logic.
2. Prefer process regex matchers and workspace-root-relative static targets.
3. Never claim shutdown success without post-shutdown process verification.

## Workspace Goal Alignment
When the active workspace is a local-first AI product stack with a desktop or browser surface,
a local backend, and model-worker subprocesses, prioritize these lifecycle checks:

- App launch should not leak backend servers, model workers, browser helpers, or download subprocesses after quit.
- Shutdown verification should cover both user-visible exit and hidden helper residue, especially Python, Node,
  uvicorn, model-runtime, and browser-automation processes.
- Restart proofs should confirm that a clean relaunch works after teardown, not only that processes disappeared.
- Process ownership should stay attributable to the active workspace intent so expected development helpers are
  distinguishable from true orphan regressions.
- Any workflow that introduces async downloads, background installs, or external tool bridges should be treated
  as high-risk for orphan-process regressions and audited accordingly.

## Hardening Addendum: Asynchronous Teardown Semantics

When a control endpoint/script triggers teardown asynchronously, treat the shutdown as a two-phase operation:

1. Trigger phase:
- Capture acceptance response (`accepted`, `pid`, `launched`, etc).

2. Verification phase:
- Poll a terminal-state probe (`status`, residue verifier, process scan) until deadline.
- Require explicit terminal signal (`STOPPED`, `verified=true`, or zero residual process count).
- Fail if deadline expires even if trigger returned success.

### Required Checks for managed-stack kill paths
- Immediate residue probe (may fail transiently).
- Delayed residue probe with bounded retries (must pass).
- Listener closure proof for managed ports.
- Restart proof after successful kill (service can return to healthy state).

### Reporting Rule
Always report three separate timestamps:
- trigger accepted time,
- terminal verification pass time,
- restart healthy time (if restart is in scope).
