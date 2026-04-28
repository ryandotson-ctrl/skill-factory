---
name: jarvis-mini-openclaw-release-guardian
description: Track and safely manage OpenClaw version lifecycle on Pi. Use when checking
  for new releases, deciding stable vs staged updates, running guarded update procedures,
  validating post-update health, and preserving rollback paths for Jarvis Mini reliability.
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Jarvis Mini Openclaw Release Guardian

Stay update-aware by default (`report_only`), and update only with explicit gates.
Always produce a rollback path before applying changes.

## Workflow
1. Collect current release telemetry.
2. Decide policy path (`report_only` or staged update).
3. Backup critical config before update.
4. Apply update in controlled window.
5. Run post-update checks and rollback if needed.

## Monitoring Commands
```bash
python3 scripts/openclaw_update_monitor.py
openclaw status --deep
openclaw channels list --json
```

## Staged Update Procedure
```bash
cp ~/.openclaw/openclaw.json ~/.openclaw/openclaw.json.bak.$(date +%Y%m%d-%H%M%S)
openclaw doctor
sudo systemctl restart openclaw
```

Then verify:
```bash
systemctl is-active openclaw
ss -ltnp | grep 18789
journalctl -u openclaw -n 120 --no-pager
```

## Rollback Trigger
Rollback immediately if any of these occur after update:
- gateway fails to listen on `127.0.0.1:18789`
- Telegram path fails persistently
- repeated crash/restart loop in `openclaw.service`

## Rollback Action
- Restore previous config backup.
- Restart `openclaw`.
- Re-run runtime checks.
- Record findings in `memory/YYYY-MM-DD.md`.

## Safety Rules
- Prefer `report_only` unless the user explicitly requests update execution.
- Never update and reconfigure multiple subsystems in one step.

## Post-Update Provider Routing Verification
After any update, verify model/provider routing before declaring success.

Minimum checks:
1. Confirm configured primary provider/model matches intended policy.
2. Confirm fallback order is present and deterministic.
3. Confirm runtime path reports the same active model/provider as configuration.
4. Confirm one live probe succeeds under the selected primary route.

If routing checks fail:
- Do not declare update success.
- Execute rollback path or hold in staged state with explicit incident notes.

## Release Evidence Bundle Requirements
A release is only complete when evidence artifacts are captured and linked.

Required evidence bundle:
- pre-update OpenClaw version and routing snapshot
- post-update OpenClaw version and routing snapshot
- service health outputs (`systemctl`, listener check, journal excerpt)
- provider/model verification output (primary + fallback order)
- rollback readiness evidence (backup location + tested command path)
- exact UTC timestamps for all artifacts

Do not claim successful rollout without this bundle.
