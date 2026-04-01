---
name: jarvis-mini-runtime-operator
description: Operate Jarvis Mini runtime on the Raspberry Pi OpenClaw stack. Use when
  checking if the bot is online, diagnosing Telegram non-responses, validating gateway/listener
  health, performing safe OpenClaw restarts, or collecting targeted runtime evidence
  for incident triage.
scope: global
portability_tier: strict_zero_leak
requires_env: []
project_profiles: []
---

# Jarvis Mini Runtime Operator

Run deterministic uptime checks first, then perform a single safe remediation if needed.
Prioritize fast checks that do not spend LLM tokens.

## Workflow
1. Gate tool actions with `python3 scripts/world_model.py gate ...` before shell/web calls.
2. Confirm Pi reachability and identity.
3. Verify OpenClaw service and gateway socket.
4. Verify Telegram bot path.
5. Run one minimal runtime probe.
6. Remediate once (`systemctl restart openclaw`) only if checks fail.
7. Re-check and report evidence with exact timestamps.

## Core Checks
Use SSH against `pi@192.168.1.106` unless the user provides a different host.

```bash
systemctl is-active openclaw
systemctl is-enabled openclaw
ss -ltnp | grep 18789
journalctl -u openclaw -n 80 --no-pager
```

## Telegram Path Check
Prefer a direct token path check when CLI probes are slow:

Environment defaults:
- `OPENCLAW_HOME=${OPENCLAW_HOME:-~/.openclaw}`
- `JARVIS_RUNTIME_HOME=${JARVIS_RUNTIME_HOME:-$OPENCLAW_HOME/workspace}`
- `TOKEN_FILE_PATH=${TOKEN_FILE_PATH:-$OPENCLAW_HOME/telegram.token}`

```bash
python3 - <<'PY'
import json, os, pathlib, urllib.request
token_path = os.environ.get(
    "TOKEN_FILE_PATH",
    str(pathlib.Path(os.environ.get("OPENCLAW_HOME", "~/.openclaw")).expanduser() / "telegram.token"),
)
token = pathlib.Path(token_path).expanduser().read_text().strip()
url = f"https://api.telegram.org/bot{token}/getMe"
print(json.loads(urllib.request.urlopen(url, timeout=10).read().decode())["result"]["username"])
PY
```

Expected username: `jarvis_mini_ai_bot`.

## Minimal Runtime Probe
Prefer one short probe instead of repeated calls:

```bash
openclaw agent --session-id <main-session-id> --message "reply with exactly OK" --json
```

If CLI commands time out over non-interactive SSH, rely on:
- `systemctl` status
- socket listener check
- targeted `journalctl` excerpts
- direct Telegram `getMe` check

## Remediation Policy
- Restart at most once per incident window:
```bash
sudo systemctl restart openclaw
sleep 3
systemctl is-active openclaw
```
- Avoid restart loops.
- Escalate with logs if restart does not recover service.

## Safety Rules
- Do not run recursive search/diff in `archive/huge_logs/`.
- Do not run destructive commands.
- Keep probes targeted and time-bounded (`timeout` for expensive CLI paths).

## Remote Host Abstraction (PI_HOST + SSH Alias)
Use portable host abstraction for all remote operations.

Canonical default:
```bash
PI_HOST=${PI_HOST:-jarvis-pi-remote}
```

Guidelines:
- Treat `jarvis-pi-remote` as the default SSH alias for remote Pi operations.
- Do not hardcode LAN-only literals in new procedures.
- Allow explicit override through `PI_HOST` when operators provide alternate hosts.

## Wrapper-First Execution Contract
Prefer guarded wrapper execution over direct SSH for runtime checks and remediations:

```bash
PI_HOST=${PI_HOST:-jarvis-pi-remote}
scripts/pi_remote_exec.sh --host "$PI_HOST" --cmd "systemctl is-active openclaw"
scripts/pi_remote_exec.sh --host "$PI_HOST" --sudo --cmd "systemctl restart openclaw"
```

Requirements:
1. Use time-bounded commands with deterministic timeout behavior.
2. Require auditable command envelopes (command, sudo flag, exit code, duration, timestamp).
3. Use direct SSH only for read-only diagnostics when wrapper path is unavailable, and report that exception explicitly.
