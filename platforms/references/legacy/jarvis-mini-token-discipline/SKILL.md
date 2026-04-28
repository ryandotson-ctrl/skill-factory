---
name: jarvis-mini-token-discipline
description: Enforce Jarvis Mini token and budget discipline on Pi. Use when token
  burn spikes, TPM headroom is low, proactive jobs are over-firing, scheduling must
  be constrained by policy, or telemetry and budget ledgers need to drive safe automation
  decisions.
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Jarvis Mini Token Discipline

Keep autonomy useful and cheap.
Route maintenance through explicit budget and headroom gates.

## Workflow
1. Refresh telemetry.
2. Measure TPM headroom and budget burn.
3. Enforce policy gates.
4. Run safe scheduler only when healthy.
5. Record evidence in telemetry files.

## Core Commands
```bash
python3 scripts/system_monitor.py
python3 scripts/token_governor_guard.py --max-wait 30
python3 scripts/budget_ledger.py --tag auto
python3 scripts/autonomy_tick.py
python3 scripts/task_scheduler.py --execute-safe
```

## Key Inputs
- `config/autonomy_policy.json`
- `memory/telemetry/budget_ledger_latest.json`
- `memory/telemetry/token_governor_guard_latest.json`
- `memory/task_queue.json`

## Load-Shedding Rules
- If TPM headroom is below policy minimum, skip proactive work.
- If system load/RAM guardrails fail, run only health/self-heal tasks.
- Keep `--execute-safe` mode for scheduler operations on Pi.

## Task Budget Classes
- `critical`: self-heal and availability checks.
- `helpful`: routine maintenance when headroom is healthy.
- `nice_to_have`: run only with abundant headroom and daily budget.

## Practical Constraints
- Avoid repeated `openclaw agent` probes for monitoring; they consume tokens.
- Prefer no-LLM scripts for health and bookkeeping.
- Keep proactive cadence bounded by policy and timers.

## Safety Rules
- Do not override policy into `FULL_AUTO` without explicit user request.
- Do not add autonomous code-changing loops in this skill.

## MLX-Primary Budget Policy Profile
When MLX is primary, enforce explicit local-first budget gates:
- Prefer local inference path for routine/autonomy tasks.
- Track MLX quality and latency signals as first-class budget inputs.
- Reserve cloud budget for fallback/escalation cases only.

Minimum policy fields to evaluate per cycle:
- `mlx_primary_enabled`
- `mlx_primary_min_success_rate`
- `mlx_primary_max_p95_latency_ms`
- `cloud_fallback_hourly_cap`
- `cloud_fallback_daily_cap`

If MLX quality floor fails, move to controlled fallback state and record reason.

## Fallback Escalation Guardrails
Fallback behavior must be deterministic, bounded, and auditable.

Rules:
1. Escalate to cloud fallback only when explicit gate conditions are met.
2. Tag each fallback event with reason code (`quality`, `timeout`, `availability`, `policy`).
3. Enforce strict per-window caps for cloud usage.
4. Recover back to MLX primary only after stability checks pass.
5. Log every transition with timestamp, state before/after, and budget impact.
