---
name: jarvis-mini-antigravity-routing
description: Manage Jarvis Mini Google Antigravity authentication and model routing
  on Pi. Use when enabling OAuth, enforcing Opus 4.6 as primary, configuring fallback
  order, diagnosing Unknown model failures, or verifying Antigravity model availability
  and quota windows.
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Jarvis Mini Antigravity Routing

Enforce deterministic model routing with Opus 4.6 first, then safe fallbacks.
Treat runtime validation as mandatory, not optional.

## Target Routing
Primary:
- `google-antigravity/claude-opus-4-6-thinking`

Fallbacks (in order):
1. `google-antigravity/gemini-3-pro-high`
2. `google-antigravity/gemini-3-flash`
3. `google/gemini-3-flash-preview`

## Workflow
1. Verify plugin + auth.
2. Apply routing.
3. Restart OpenClaw.
4. Verify model list and runtime execution.
5. If runtime says `Unknown model`, apply hotfix and re-check.

## Auth and Provider Checks
```bash
openclaw plugins enable google-antigravity-auth
openclaw models auth status --provider google-antigravity --json
openclaw channels list --json
```

## Apply Routing
Prefer OpenClaw config commands:
```bash
openclaw config set agents.defaults.model.primary "google-antigravity/claude-opus-4-6-thinking"
openclaw config set agents.defaults.model.fallbacks '["google-antigravity/gemini-3-pro-high","google-antigravity/gemini-3-flash","google/gemini-3-flash-preview"]'
sudo systemctl restart openclaw
```

## Runtime Validation
```bash
openclaw models list --provider google-antigravity --all --json
openclaw models status --json
journalctl -u openclaw -n 120 --no-pager | grep -i "Unknown model" || true
```

## Resolver Mismatch Recovery
If Opus 4.6 is configured but runtime rejects it:
```bash
${JARVIS_RUNTIME_HOME:-${OPENCLAW_HOME:-~/.openclaw}/workspace}/scripts/pi_antigravity_opus46_hotfix.sh
```
or run the startup guard manually:
```bash
sudo systemctl start jarvis-opus46-selfcheck.service
```

## Non-Goals
- Do not enable Mac compute/offload/tunnels.
- Do not change the primary away from Opus 4.6 unless the user explicitly asks.

## Safety Rules
- Do not paste OAuth callback URLs into chat logs.
- Keep secrets in OpenClaw auth storage, not git-tracked files.
