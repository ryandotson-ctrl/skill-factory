---
name: jarvis-mini-ears-guardrails
description: Harden Jarvis Mini Ears sleep-apnea and ambient monitoring on Pi. Use
  when preserving health-related checks with minimal token burn, tuning Ears thresholds,
  validating timer behavior, preventing runaway tasks, and debugging missed or noisy
  Ears alerts.
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Jarvis Mini Ears Guardrails

Keep both Ears jobs active and cheap:
- Sleep monitor every 5 minutes.
- Ambient scout every 30 minutes.

## Workflow
1. Verify timers/services.
2. Verify policy thresholds.
3. Run one forced/manual tick when debugging.
4. Check telemetry outputs and alert cooldown state.
5. Adjust only conservative thresholds.

## Timer Checks
```bash
systemctl status --no-pager jarvis-ears-sleep.timer
systemctl status --no-pager jarvis-ears-ambient.timer
systemctl list-timers --all | grep -E "jarvis-ears-(sleep|ambient)"
```

## Manual Tick Commands
```bash
python3 scripts/ears_sleep_apnea_tick.py --force
python3 scripts/ears_ambient_scout_tick.py
```

## Files to Inspect
- `config/autonomy_policy.json` (`ears.sleep_apnea` and `ears.ambient_scout`)
- `memory/telemetry/ears_sleep_latest.json`
- `memory/telemetry/ears_ambient_latest.json`
- `memory/limits/ears_sleep_state.json`
- `memory/limits/ears_ambient_state.json`

## Anti-Runaway Policy
- Keep Ears scripts token-free (no LLM calls, no transcription loops).
- Enforce alert cooldowns via state files.
- Avoid high-frequency retries after recording failures.
- Do not convert Ears into free-running agent turns.

## Reliability Notes
- Ears depends on microphone device access (`arecord`).
- Prefer targeted diagnosis from latest telemetry and one fresh run.
- Keep notifications actionable and sparse.

## Safety Rules
- Treat output as heuristic wellness monitoring, not medical diagnosis.
- Keep sleep/ambient checks enabled unless the user explicitly requests otherwise.
